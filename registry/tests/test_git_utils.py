import subprocess
import base64
from email.message import Message
from io import BytesIO
import urllib.error

import pytest

from astrbot_registry.utils import git_utils
from astrbot_registry.utils.git_utils import GitError, clone_repo, preflight_github_repo_size
from astrbot_registry.services.git_providers import GitCredential, get_git_provider_for_url
from astrbot_registry.services.git_providers.github import (
    _github_access_denied_message,
    _github_error_message,
)


def test_clone_repo_adds_http_proxy_config(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    clone_repo(
        "https://github.com/example/repo",
        tmp_path / "repo",
        timeout=10,
        allowed_hosts=["github.com"],
        proxy_url="http://proxy.example:1080",
    )

    assert calls == [
        [
            "git",
            "-c",
            "http.proxy=http://proxy.example:1080",
            "-c",
            "https.proxy=http://proxy.example:1080",
            "clone",
            "--filter=blob:none",
            "--depth",
            "1",
            "https://github.com/example/repo",
            str(tmp_path / "repo"),
        ]
    ]


def test_clone_repo_keeps_full_clone_for_commit_sha(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ref = "a" * 40

    clone_repo(
        "https://github.com/example/repo",
        tmp_path / "repo",
        ref=ref,
        timeout=10,
        allowed_hosts=["github.com"],
    )

    assert calls == [
        ["git", "clone", "https://github.com/example/repo", str(tmp_path / "repo")],
        ["git", "-C", str(tmp_path / "repo"), "checkout", ref],
    ]


def test_clone_repo_uses_temporary_token_without_putting_it_in_command(monkeypatch, tmp_path) -> None:
    calls = []
    envs = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        envs.append(kwargs.get("env"))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    clone_repo(
        "https://github.com/example/private",
        tmp_path / "repo",
        timeout=10,
        allowed_hosts=["github.com"],
        github_token="ghp_secret",
    )

    assert "ghp_secret" not in " ".join(calls[0])
    assert envs[0]["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
    assert envs[0]["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    encoded = envs[0]["GIT_CONFIG_VALUE_0"].removeprefix("Authorization: Basic ")
    assert base64.b64decode(encoded).decode() == "x-access-token:ghp_secret"
    assert envs[0]["GIT_TERMINAL_PROMPT"] == "0"


def test_github_provider_detects_embedded_refs() -> None:
    provider = get_git_provider_for_url(
        "https://github.com/example/repo/tree/release/v1",
        allowed_hosts=["github.com"],
    )

    normalized = provider.normalize_url(
        "https://github.com/example/repo/tree/release/v1",
        allowed_hosts=["github.com"],
    )

    assert normalized.provider == "github"
    assert normalized.repo_url == "https://github.com/example/repo"
    assert normalized.detected_ref_type == "branch"
    assert normalized.detected_ref == "release/v1"


def test_github_provider_clone_uses_provider_credential(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_clone_repo(*args, **kwargs):
        calls.append((args, kwargs))

    provider = get_git_provider_for_url("https://github.com/example/repo", allowed_hosts=["github.com"])
    monkeypatch.setattr("astrbot_registry.services.git_providers.github.clone_repo", fake_clone_repo)

    provider.clone_repo(
        "https://github.com/example/repo",
        tmp_path / "repo",
        credential=GitCredential(temporary_token="ghp_secret"),
        ref="main",
        timeout=10,
        allowed_hosts=["github.com"],
        proxy_url=None,
    )

    assert calls[0][1]["github_token"] == "ghp_secret"


def test_github_error_message_reads_json_body() -> None:
    headers = Message()
    error = urllib.error.HTTPError(
        "https://api.github.com/repos/example/repo",
        403,
        "Forbidden",
        headers,
        BytesIO(b'{"message":"Resource not accessible by personal access token"}'),
    )

    assert _github_error_message(error) == "Resource not accessible by personal access token"


@pytest.mark.parametrize(
    ("status_code", "github_message", "expected"),
    [
        (401, "Bad credentials", "GitHub token is invalid or expired; check the token value"),
        (
            403,
            "Resource not accessible by personal access token",
            "GitHub token cannot access this repository; grant repository Contents read permission",
        ),
        (
            403,
            "API rate limit exceeded for 1.2.3.4",
            "GitHub API rate limit exceeded; add a token or wait before retrying",
        ),
    ],
)
def test_github_access_denied_messages(status_code: int, github_message: str, expected: str) -> None:
    assert _github_access_denied_message(status_code, github_message) == expected


def test_preflight_github_repo_size_rejects_oversized_repo(monkeypatch) -> None:
    monkeypatch.setattr(git_utils, "fetch_github_repo_size_kb", lambda *args, **kwargs: 2049)

    with pytest.raises(GitError, match="Repository is too large"):
        preflight_github_repo_size(
            "https://github.com/example/repo",
            max_size_kb=2048,
            allowed_hosts=["github.com"],
        )


def test_preflight_github_repo_size_can_be_disabled(monkeypatch) -> None:
    def fail_fetch(*args, **kwargs):
        raise AssertionError("fetch should not be called")

    monkeypatch.setattr(git_utils, "fetch_github_repo_size_kb", fail_fetch)

    assert preflight_github_repo_size(
        "https://github.com/example/repo",
        max_size_kb=0,
        allowed_hosts=["github.com"],
    ) is None
