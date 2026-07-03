import uuid
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from astrbot_registry.api import admin
from astrbot_registry.schemas.admin import PluginCreateRequest


@pytest.mark.asyncio
async def test_submit_plugin_queues_submit_task(monkeypatch) -> None:
    enqueued = {}

    async def fake_enqueue(background_tasks, task_type, payload, db):
        enqueued["task_type"] = task_type
        enqueued["payload"] = payload

    monkeypatch.setattr(admin, "runtime_git_allowed_hosts", async_value(["github.com"]))
    monkeypatch.setattr(admin, "parse_github_url", lambda *args, **kwargs: ("example", "repo"))
    monkeypatch.setattr(admin, "_enqueue_or_fallback", fake_enqueue)

    user_id = uuid.uuid4()
    result = await admin.submit_plugin(
        PluginCreateRequest(
            repo_url="https://github.com/example/astrbot_plugin_test",
            version="v2",
            ref="main",
        ),
        BackgroundTasks(),
        db=object(),
        current_user=SimpleNamespace(id=user_id),
    )

    assert result == {"plugin_id": None, "version": "v2", "status": "queued"}
    assert enqueued["task_type"] == "submit"
    assert enqueued["payload"] == {
        "repo_url": "https://github.com/example/astrbot_plugin_test",
        "version": "v2",
        "ref": "main",
        "user_id": str(user_id),
    }


@pytest.mark.asyncio
async def test_submit_plugin_rejects_invalid_repo_url(monkeypatch) -> None:
    monkeypatch.setattr(admin, "runtime_git_allowed_hosts", async_value(["github.com"]))

    def fake_parse(*args, **kwargs):
        raise ValueError("Invalid GitHub URL")

    monkeypatch.setattr(admin, "parse_github_url", fake_parse)

    with pytest.raises(HTTPException) as exc:
        await admin.submit_plugin(
            PluginCreateRequest(repo_url="https://example.com/repo"),
            BackgroundTasks(),
            db=object(),
            current_user=SimpleNamespace(id=uuid.uuid4()),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid GitHub URL"


def async_value(value):
    async def inner(*args, **kwargs):
        return value

    return inner
