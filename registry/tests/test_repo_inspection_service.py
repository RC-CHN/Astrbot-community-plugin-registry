from types import SimpleNamespace

import pytest

from astrbot_registry.services import repo_inspection_service
from astrbot_registry.services.git_providers import NormalizedRepo


class FakeProvider:
    def __init__(self):
        self.tokens: list[str | None] = []

    def normalize_url(self, repo_url, *, allowed_hosts=None):
        return NormalizedRepo(
            provider="github",
            repo_url="https://github.com/example/repo",
            owner="example",
            repo="repo",
            host="github.com",
        )

    def inspect_repo(self, repo, *, credential, ref_type, ref, include_refs, proxy_url, timeout):
        self.tokens.append(credential.temporary_token)
        return {
            "provider": "github",
            "repo_url": repo.repo_url,
            "owner": repo.owner,
            "repo": repo.repo,
            "host": repo.host,
            "private": False,
            "default_branch": "main",
            "size_kb": 1,
            "updated_at": None,
            "detected_ref_type": None,
            "detected_ref": None,
            "selected_ref_type": "default",
            "selected_ref": "main",
            "selected_commit": {"sha": "a" * 40},
            "metadata": {
                "name": "astrbot_plugin_test",
                "plugin_key": "astrbot-plugin-test",
                "display_name": None,
                "desc": "test",
                "author": "tester",
                "version": "v1.0.0",
                "repo": None,
                "tags": [],
                "astrbot_version": None,
            },
            "branches": [],
            "tags": [],
        }


@pytest.mark.asyncio
async def test_inspect_git_repo_uses_global_github_token_when_no_request_token(monkeypatch) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(repo_inspection_service, "get_git_provider_for_url", lambda *args, **kwargs: provider)
    monkeypatch.setattr(repo_inspection_service, "runtime_github_token", async_value("global_token"))
    monkeypatch.setattr(repo_inspection_service, "get_plugin_by_key", async_value(None))

    result = await repo_inspection_service.inspect_git_repo(
        SimpleNamespace(),
        repo_url="https://github.com/example/repo",
    )

    assert provider.tokens == ["global_token"]
    assert result["match"]["status"] == "new_plugin"


@pytest.mark.asyncio
async def test_inspect_git_repo_prefers_request_token(monkeypatch) -> None:
    provider = FakeProvider()
    monkeypatch.setattr(repo_inspection_service, "get_git_provider_for_url", lambda *args, **kwargs: provider)
    monkeypatch.setattr(repo_inspection_service, "runtime_github_token", async_value("global_token"))
    monkeypatch.setattr(repo_inspection_service, "get_plugin_by_key", async_value(None))

    await repo_inspection_service.inspect_git_repo(
        SimpleNamespace(),
        repo_url="https://github.com/example/repo",
        temporary_token="request_token",
    )

    assert provider.tokens == ["request_token"]


def async_value(value):
    async def inner(*args, **kwargs):
        return value

    return inner
