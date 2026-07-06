import pytest

from astrbot_registry.models import Plugin, Tag
from astrbot_registry.services import plugin_service
from astrbot_registry.schemas.plugin import PluginUpdate
from astrbot_registry.utils.metadata_parser import PluginMetadata


@pytest.mark.asyncio
async def test_create_plugin_assigns_tags_before_session_add(monkeypatch) -> None:
    events: list[str] = []

    class FakeDB:
        def add(self, item):
            events.append("add")
            assert [tag.name for tag in item.tags] == ["acprctl"]

        async def flush(self):
            events.append("flush")

        async def refresh(self, item, attrs=None):
            events.append("refresh")

        async def commit(self):
            events.append("commit")

    async def fake_get_plugin_by_key(db, plugin_key):
        return None

    async def fake_ensure_tags(db, names):
        events.append("ensure_tags")
        return [Tag(name="acprctl")]

    async def fake_refresh_cache(db):
        events.append("refresh_cache")

    monkeypatch.setattr(plugin_service, "get_plugin_by_key", fake_get_plugin_by_key)
    monkeypatch.setattr(plugin_service, "_ensure_tags", fake_ensure_tags)
    monkeypatch.setattr(plugin_service, "_refresh_registry_cache", fake_refresh_cache)

    await plugin_service.create_plugin(
        FakeDB(),
        PluginMetadata(
            name="astrbot_plugin_acprctl_e2e",
            author="tester",
            version="0.1.0",
            tags=["acprctl"],
        ),
        repo_url="https://example.invalid/plugin.git",
    )

    assert events.index("ensure_tags") < events.index("add")


@pytest.mark.asyncio
async def test_update_plugin_refreshes_tags_before_assignment(monkeypatch) -> None:
    events: list[str] = []

    class FakeDB:
        async def refresh(self, item, attrs=None):
            events.append(f"refresh:{attrs}")

        async def commit(self):
            events.append("commit")

    async def fake_ensure_tags(db, names):
        events.append("ensure_tags")
        return [Tag(name="updated")]

    async def fake_refresh_cache(db):
        events.append("refresh_cache")

    monkeypatch.setattr(plugin_service, "_ensure_tags", fake_ensure_tags)
    monkeypatch.setattr(plugin_service, "_refresh_registry_cache", fake_refresh_cache)

    plugin = Plugin(
        plugin_key="astrbot-plugin-acprctl-e2e",
        display_name="ACPRCTL E2E",
        description="temporary",
        author="tester",
        repo_url="https://example.invalid/plugin.git",
        status="pending",
    )
    plugin.tags = []

    await plugin_service.update_plugin(
        FakeDB(),
        plugin,
        PluginUpdate(tags=["updated"]),
    )

    assert events[:2] == ["refresh:['tags']", "ensure_tags"]
    assert [tag.name for tag in plugin.tags] == ["updated"]
