import hashlib
import uuid

from astrbot_registry.models import Plugin, PluginVersion, SecurityScan
from astrbot_registry.services.registry_service import (
    _format_entry,
    _get_latest,
    canonical_registry_bytes,
)


def _plugin() -> Plugin:
    plugin = Plugin(
        id=uuid.uuid4(),
        plugin_key="astrbot-plugin-test",
        display_name="Test",
        description="desc",
        author="tester",
        repo_url=None,
        status="active",
    )
    plugin.tags = []
    plugin.i18n_entries = []
    return plugin


def _version(*, scanned: bool, build_status: str = "success") -> PluginVersion:
    version = PluginVersion(
        id=uuid.uuid4(),
        plugin_id=uuid.uuid4(),
        version="v1.0.0",
        source_type="manual_upload",
        download_url="https://example.test/plugin.zip",
        s3_key="plugins/test.zip",
        file_size=100,
        build_status=build_status,
        version_status="active",
        is_latest=True,
    )
    if scanned:
        version.scan = SecurityScan(
            version_id=version.id,
            virustotal_pass=True,
            llm_agent_pass=True,
        )
    return version


def test_latest_requires_successful_build_and_scan() -> None:
    assert _get_latest([_version(scanned=False)]) is None
    assert _get_latest([_version(scanned=True, build_status="failed")]) is None
    assert _get_latest([_version(scanned=True)]) is not None


def test_registry_entry_keeps_official_shape() -> None:
    plugin = _plugin()
    version = _version(scanned=True)
    entry = _format_entry(plugin, version)

    assert entry["desc"] == "desc"
    assert entry["repo"] is None
    assert entry["download_url"] == "https://example.test/plugin.zip"
    assert entry["sec_scan"]["virustotal"]["pass"] is True


def test_canonical_registry_bytes_are_stable() -> None:
    registry = {"b": {"name": "插件"}, "a": {"version": "v1"}}
    payload = canonical_registry_bytes(registry)

    assert payload == b'{"a":{"version":"v1"},"b":{"name":"\xe6\x8f\x92\xe4\xbb\xb6"}}'
    assert hashlib.md5(payload).hexdigest() == hashlib.md5(
        canonical_registry_bytes({"a": {"version": "v1"}, "b": {"name": "插件"}})
    ).hexdigest()
