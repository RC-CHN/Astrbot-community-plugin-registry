from types import SimpleNamespace
import uuid
import zipfile

import pytest

from astrbot_registry.models import Plugin
from astrbot_registry.services import build_service


async def _async_value(value):
    return value


class FakeDB:
    async def commit(self):
        pass


class FakeProvider:
    def __init__(self, metadata_version: str):
        self.metadata_version = metadata_version

    def preflight_repo_size(self, *args, **kwargs):
        return 1

    def clone_repo(self, repo_url, dest, **kwargs):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "metadata.yaml").write_text(
            "\n".join(
                [
                    "name: phimg",
                    "desc: test plugin",
                    "author: muyni233",
                    f"version: {self.metadata_version}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (dest / "main.py").write_text("print('ok')\n", encoding="utf-8")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested_version", "expected_version"),
    [(None, "v1.0.0"), ("v1.0.1", "v1.0.1")],
)
async def test_build_from_repo_uses_metadata_version_unless_overridden(
    monkeypatch, requested_version, expected_version
) -> None:
    created = {}
    uploaded = {}
    updated = {}

    plugin = Plugin(
        id=uuid.uuid4(),
        plugin_key="phimg",
        display_name="Philomena API 搜图",
        description="test plugin",
        author="muyni233",
        repo_url="https://github.com/muyni233/astrbot_plugin_phimg",
    )

    async def fake_create_version(**kwargs):
        created.update(kwargs)
        return SimpleNamespace(id=uuid.uuid4(), build_status=kwargs["build_status"], build_log=None)

    async def fake_upload_file(zip_path, s3_key):
        with zipfile.ZipFile(zip_path) as zf:
            uploaded["metadata"] = zf.read("metadata.yaml").decode("utf-8")
        uploaded["s3_key"] = s3_key

    async def fake_update_version_after_build(**kwargs):
        updated.update(kwargs)

    monkeypatch.setattr(
        build_service,
        "runtime_s3_layout",
        lambda _db: _async_value({"plugins_prefix": "plugins", "unknown_author": "unknown"}),
    )
    monkeypatch.setattr(build_service, "runtime_s3_public_url", lambda _db: _async_value("https://cdn.example"))
    monkeypatch.setattr(build_service, "runtime_git_clone_timeout", lambda _db: _async_value(30))
    monkeypatch.setattr(build_service, "runtime_git_preflight_timeout", lambda _db: _async_value(10))
    monkeypatch.setattr(build_service, "runtime_git_max_repo_size_kb", lambda _db: _async_value(1024))
    monkeypatch.setattr(build_service, "runtime_git_allowed_hosts", lambda _db: _async_value(["github.com"]))
    monkeypatch.setattr(build_service, "runtime_git_http_proxy", lambda _db: _async_value(""))
    monkeypatch.setattr(build_service, "runtime_github_token", lambda _db: _async_value(""))
    monkeypatch.setattr(build_service, "runtime_max_release_zip_bytes", lambda _db: _async_value(1024 * 1024))
    monkeypatch.setattr(build_service, "get_git_provider_for_url", lambda *args, **kwargs: FakeProvider("v1.0.0"))
    monkeypatch.setattr(build_service, "get_commit_sha", lambda _repo_dir: "8" * 40)
    monkeypatch.setattr(build_service, "get_version_by_plugin_and_commit", lambda *args, **kwargs: _async_value(None))
    monkeypatch.setattr("astrbot_registry.services.plugin_service.create_version", fake_create_version)
    monkeypatch.setattr(build_service, "upload_file", fake_upload_file)
    monkeypatch.setattr(build_service, "update_version_after_build", fake_update_version_after_build)
    monkeypatch.setattr(build_service, "scan_version", lambda *args, **kwargs: _async_value(None))

    await build_service.build_from_repo(
        FakeDB(),
        plugin,
        requested_version,
        ref="8" * 40,
        changelog="notes",
    )

    assert created["version"] == expected_version
    assert created["changelog"] == "notes"
    assert updated["metadata"].version == expected_version
    assert f"version: {expected_version}" in uploaded["metadata"]
    assert f"/{expected_version}/" in uploaded["s3_key"]
