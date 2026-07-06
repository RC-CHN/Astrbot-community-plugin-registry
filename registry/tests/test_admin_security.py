from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from astrbot_registry.api import admin
from astrbot_registry.schemas.admin import UserCreate


class FakeRequest:
    headers = {}

    async def body(self) -> bytes:
        return b"{}"


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
