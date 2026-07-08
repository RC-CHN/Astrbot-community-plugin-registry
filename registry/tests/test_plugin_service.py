import uuid

import pytest

from astrbot_registry.models import Plugin, Tag
from astrbot_registry.services import plugin_service
from astrbot_registry.schemas.plugin import PluginUpdate
from astrbot_registry.utils.metadata_parser import PluginMetadata


async def _async_value(value):
    return value


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
async def test_create_version_allows_duplicate_metadata_version(monkeypatch) -> None:
    added = []

    class FakeDB:
        def add(self, item):
            added.append(item)

        async def commit(self):
            pass

        async def refresh(self, item):
            pass

    async def fake_refresh_cache(db):
        pass

    monkeypatch.setattr(plugin_service, "_refresh_registry_cache", fake_refresh_cache)
    plugin = Plugin(
        id=uuid.uuid4(),
        plugin_key="astrbot-plugin-acprctl-e2e",
        display_name="ACPRCTL E2E",
        description="temporary",
        author="tester",
        repo_url="https://example.invalid/plugin.git",
        status="pending",
    )
    metadata = PluginMetadata(name=plugin.plugin_key, author=plugin.author, version="1.0.0")

    first = await plugin_service.create_version(
        FakeDB(),
        plugin,
        version="1.0.0",
        metadata=metadata,
        s3_key="plugins/test/1.0.0/first.zip",
        download_url="https://example.invalid/first.zip",
        file_size=1,
        source_type="git_auto",
        commit_sha="1" * 40,
    )
    second = await plugin_service.create_version(
        FakeDB(),
        plugin,
        version="1.0.0",
        metadata=metadata,
        s3_key="plugins/test/1.0.0/second.zip",
        download_url="https://example.invalid/second.zip",
        file_size=1,
        source_type="git_auto",
        commit_sha="2" * 40,
    )

    assert first.version == second.version == "1.0.0"
    assert first.commit_sha != second.commit_sha
    assert len(added) == 2


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


@pytest.mark.asyncio
async def test_delete_version_removes_artifact(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    plugin_id = uuid.uuid4()
    version = plugin_service.PluginVersion(
        id=uuid.uuid4(),
        plugin_id=plugin_id,
        version="v1.0.0",
        s3_key="plugins/test.zip",
    )

    class FakeDB:
        async def execute(self, statement):
            events.append(("execute", statement))

        async def commit(self):
            events.append(("commit", None))

    async def fake_delete_file(s3_key):
        events.append(("delete_file", s3_key))

    async def fake_refresh_cache(db):
        events.append(("refresh_cache", None))

    monkeypatch.setattr(plugin_service, "get_version", lambda _db, _version_id: _async_value(version))
    monkeypatch.setattr(plugin_service, "delete_file", fake_delete_file)
    monkeypatch.setattr(plugin_service, "_refresh_registry_cache", fake_refresh_cache)

    deleted = await plugin_service.delete_version(FakeDB(), plugin_id, version.id)

    assert deleted is version
    assert events[0] == ("delete_file", "plugins/test.zip")
    assert events[1][0] == "execute"
    assert events[2:] == [("commit", None), ("refresh_cache", None)]


@pytest.mark.asyncio
async def test_delete_plugin_removes_all_version_artifacts(monkeypatch) -> None:
    events: list[tuple[str, object]] = []
    plugin_id = uuid.uuid4()
    plugin = Plugin(id=plugin_id, plugin_key="phimg", display_name="phimg", author="muyni233")

    class FakeScalars:
        def __iter__(self):
            return iter(["plugins/one.zip", None, "plugins/two.zip"])

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeDB:
        async def execute(self, statement):
            events.append(("execute", statement))
            return FakeResult()

        async def delete(self, item):
            events.append(("delete", item))

        async def commit(self):
            events.append(("commit", None))

    async def fake_delete_file(s3_key):
        events.append(("delete_file", s3_key))

    async def fake_refresh_cache(db):
        events.append(("refresh_cache", None))

    monkeypatch.setattr(plugin_service, "get_plugin", lambda _db, _plugin_id: _async_value(plugin))
    monkeypatch.setattr(plugin_service, "delete_file", fake_delete_file)
    monkeypatch.setattr(plugin_service, "_refresh_registry_cache", fake_refresh_cache)

    deleted = await plugin_service.delete_plugin(FakeDB(), plugin_id)

    assert deleted is plugin
    assert ("delete_file", "plugins/one.zip") in events
    assert ("delete_file", "plugins/two.zip") in events
    assert ("delete", plugin) in events
    assert events[-2:] == [("commit", None), ("refresh_cache", None)]
