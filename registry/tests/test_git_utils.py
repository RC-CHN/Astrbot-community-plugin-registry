import subprocess

import pytest

from astrbot_registry.utils import git_utils
from astrbot_registry.utils.git_utils import GitError, clone_repo, preflight_github_repo_size


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
