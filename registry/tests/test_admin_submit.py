import uuid
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks

from astrbot_registry.api import admin
from astrbot_registry.schemas.admin import PluginCreateRequest
from astrbot_registry.services.errors import ConflictError
from astrbot_registry.utils.metadata_parser import PluginMetadata


@pytest.mark.asyncio
async def test_submit_existing_plugin_queues_new_version(monkeypatch) -> None:
    plugin = SimpleNamespace(
        id=uuid.uuid4(),
        plugin_key="astrbot-plugin-test",
        author="tester",
    )
    enqueued = {}

    async def fake_enqueue(background_tasks, task_type, payload, db):
        enqueued["task_type"] = task_type
        enqueued["payload"] = payload

    async def fake_get_plugin_by_key(db, plugin_key):
        return plugin

    async def fake_no_version(db, plugin_id, version):
        return None

    monkeypatch.setattr(admin, "clone_repo", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "runtime_git_clone_timeout", async_value(120))
    monkeypatch.setattr(admin, "runtime_git_allowed_hosts", async_value(["github.com"]))
    monkeypatch.setattr(
        admin,
        "parse_metadata_yaml",
        lambda path: PluginMetadata(name="astrbot_plugin_test", author="tester", version="v2"),
    )
    monkeypatch.setattr(admin, "get_plugin_by_key", fake_get_plugin_by_key)
    monkeypatch.setattr(admin, "get_version_by_plugin_and_number", fake_no_version)
    monkeypatch.setattr(admin, "create_plugin", fail_if_called)
    monkeypatch.setattr(admin, "_enqueue_or_fallback", fake_enqueue)

    result = await admin.submit_plugin(
        PluginCreateRequest(repo_url="https://github.com/example/astrbot_plugin_test"),
        BackgroundTasks(),
        db=object(),
        current_user=SimpleNamespace(id=uuid.uuid4()),
    )

    assert result == {"plugin_id": str(plugin.id), "version": "v2", "status": "queued"}
    assert enqueued["task_type"] == "build"
    assert enqueued["payload"]["plugin_id"] == str(plugin.id)


@pytest.mark.asyncio
async def test_submit_existing_plugin_rejects_existing_version(monkeypatch) -> None:
    plugin = SimpleNamespace(
        id=uuid.uuid4(),
        plugin_key="astrbot-plugin-test",
        author="tester",
    )

    async def fake_get_plugin_by_key(db, plugin_key):
        return plugin

    async def fake_existing_version(db, plugin_id, version):
        return object()

    monkeypatch.setattr(admin, "clone_repo", lambda *args, **kwargs: None)
    monkeypatch.setattr(admin, "runtime_git_clone_timeout", async_value(120))
    monkeypatch.setattr(admin, "runtime_git_allowed_hosts", async_value(["github.com"]))
    monkeypatch.setattr(
        admin,
        "parse_metadata_yaml",
        lambda path: PluginMetadata(name="astrbot_plugin_test", author="tester", version="v1"),
    )
    monkeypatch.setattr(admin, "get_plugin_by_key", fake_get_plugin_by_key)
    monkeypatch.setattr(admin, "get_version_by_plugin_and_number", fake_existing_version)

    with pytest.raises(ConflictError):
        await admin.submit_plugin(
            PluginCreateRequest(repo_url="https://github.com/example/astrbot_plugin_test"),
            BackgroundTasks(),
            db=object(),
            current_user=SimpleNamespace(id=uuid.uuid4()),
        )


def async_value(value):
    async def inner(*args, **kwargs):
        return value

    return inner


async def fail_if_called(*args, **kwargs):
    raise AssertionError("unexpected call")
