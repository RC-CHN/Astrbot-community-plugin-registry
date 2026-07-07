import subprocess

from astrbot_registry.utils.git_utils import clone_repo


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
            "--depth",
            "1",
            "https://github.com/example/repo",
            str(tmp_path / "repo"),
        ]
    ]
