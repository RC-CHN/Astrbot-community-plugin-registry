import hashlib
import hmac
import json
from types import SimpleNamespace
import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException

from astrbot_registry.api import admin
from astrbot_registry.models import Plugin
from astrbot_registry.schemas.admin import UserCreate


class FakeRequest:
    def __init__(self, body: bytes = b"{}", headers: dict[str, str] | None = None) -> None:
        self._body = body
        self.headers = headers or {}

    async def body(self) -> bytes:
        return self._body


@pytest.mark.asyncio
async def test_bootstrap_api_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.setattr(admin.settings, "bootstrap_api_enabled", False)

    with pytest.raises(HTTPException) as exc:
        await admin.bootstrap_user(
            UserCreate(
                username="admin",
                password="strong-password",
                role="admin",
            ),
            db=object(),  # type: ignore[arg-type]
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Bootstrap API is disabled"


@pytest.mark.asyncio
async def test_github_webhook_requires_configured_secret(monkeypatch) -> None:
    async def empty_webhook_secret(db):
        return ""

    async def webhook_auto_version(db):
        return "auto"

    class FakeSession:
        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(admin.settings, "github_webhook_require_secret", True)
    monkeypatch.setattr(admin, "runtime_webhook_secret", empty_webhook_secret)
    monkeypatch.setattr(admin, "runtime_webhook_auto_version", webhook_auto_version)
    monkeypatch.setattr(admin, "async_session", lambda: FakeSession())

    with pytest.raises(HTTPException) as exc:
        await admin.github_webhook(FakeRequest(), BackgroundTasks())  # type: ignore[arg-type]

    assert exc.value.status_code == 503
    assert exc.value.detail == "GitHub webhook secret is not configured"


@pytest.mark.asyncio
async def test_github_webhook_rejects_invalid_signature(monkeypatch) -> None:
    db = FakeWebhookDB(plugin=_plugin())
    monkeypatch_webhook_runtime(monkeypatch, db)

    with pytest.raises(HTTPException) as exc:
        await admin.github_webhook(
            FakeRequest(_webhook_body(), {"X-Hub-Signature-256": "sha256=bad"}),
            BackgroundTasks(),
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid webhook signature"
    assert db.added == []


@pytest.mark.asyncio
async def test_github_webhook_ignores_unregistered_repo(monkeypatch) -> None:
    db = FakeWebhookDB(plugin=None)
    enqueued = {}
    monkeypatch_webhook_runtime(monkeypatch, db, enqueued)

    body = _webhook_body()
    result = await admin.github_webhook(
        FakeRequest(body, {"X-Hub-Signature-256": _signature(body)}),
        BackgroundTasks(),
    )

    assert result == {"status": "ignored"}
    assert enqueued == {}
    assert len(db.added) == 1
    event = db.added[0]
    assert event.status == "ignored"
    assert event.event_type == "push"
    assert "repository is not registered" in event.error_message


@pytest.mark.asyncio
async def test_github_webhook_queues_build_for_registered_repo(monkeypatch) -> None:
    plugin = _plugin()
    db = FakeWebhookDB(plugin=plugin)
    enqueued = {}
    monkeypatch_webhook_runtime(monkeypatch, db, enqueued)

    body = _webhook_body()
    result = await admin.github_webhook(
        FakeRequest(body, {"X-Hub-Signature-256": _signature(body)}),
        BackgroundTasks(),
    )

    assert result == {"status": "queued"}
    assert len(db.added) == 1
    event = db.added[0]
    assert event.plugin_id == plugin.id
    assert event.event_type == "push"
    assert event.status == "success"
    assert event.payload == json.loads(body)
    assert enqueued == {
        "task_type": "build",
        "payload": {
            "plugin_id": str(plugin.id),
            "version": "auto",
            "ref": "main",
            "changelog": "",
            "user_id": "",
        },
    }


def test_github_webhook_http_route_queues_registered_repo(monkeypatch, client) -> None:
    plugin = _plugin()
    db = FakeWebhookDB(plugin=plugin)
    enqueued = {}
    monkeypatch_webhook_runtime(monkeypatch, db, enqueued)

    body = _webhook_body()
    response = client.post(
        "/api/v1/admin/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _signature(body),
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "queued"}
    assert enqueued["task_type"] == "build"
    assert enqueued["payload"]["plugin_id"] == str(plugin.id)
    assert enqueued["payload"]["ref"] == "main"


def monkeypatch_webhook_runtime(monkeypatch, db, enqueued=None) -> None:
    async def webhook_secret(_db):
        return "secret"

    async def webhook_auto_version(_db):
        return "auto"

    async def fake_enqueue(_background_tasks, task_type, payload, _db):
        if enqueued is not None:
            enqueued["task_type"] = task_type
            enqueued["payload"] = payload

    monkeypatch.setattr(admin.settings, "github_webhook_require_secret", True)
    monkeypatch.setattr(admin, "runtime_webhook_secret", webhook_secret)
    monkeypatch.setattr(admin, "runtime_webhook_auto_version", webhook_auto_version)
    monkeypatch.setattr(admin, "async_session", lambda: FakeSession(db))
    monkeypatch.setattr(admin, "_enqueue_or_fallback", fake_enqueue)


class FakeSession:
    def __init__(self, db) -> None:
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeWebhookDB:
    def __init__(self, plugin) -> None:
        self.plugin = plugin
        self.added = []

    async def execute(self, _statement):
        return FakeResult(self.plugin)

    def add(self, item) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        return None


class FakeResult:
    def __init__(self, plugin) -> None:
        self.plugin = plugin

    def scalar_one_or_none(self):
        return self.plugin


def _webhook_body() -> bytes:
    return json.dumps(
        {
            "repository": {
                "html_url": "https://github.com/example/astrbot_plugin_demo",
            },
            "ref": "refs/heads/main",
        },
        separators=(",", ":"),
    ).encode("utf-8")


def _signature(body: bytes) -> str:
    return "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()


def _plugin() -> Plugin:
    return Plugin(
        id=uuid.uuid4(),
        plugin_key="astrbot_plugin_demo",
        display_name="Demo",
        description="Demo plugin",
        author="tester",
        repo_url="https://github.com/example/astrbot_plugin_demo",
        status="active",
        review_status="approved",
    )
