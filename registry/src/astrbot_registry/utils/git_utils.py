"""GitHub URL parsing and repository cloning helpers."""

import re
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator


class GitError(RuntimeError):
    """Raised when a git operation fails."""


_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
    re.IGNORECASE,
)


def parse_github_url(url: str) -> tuple[str, str]:
    """Return (owner, repo) from a GitHub HTTPS URL."""
    match = _GITHUB_URL_RE.match(url)
    if not match:
        raise ValueError(f"Invalid GitHub URL: {url}")
    return match.group(1), match.group(2)


def _is_sha(ref: str) -> bool:
    return len(ref) == 40 and all(c in "0123456789abcdef" for c in ref.lower())


def clone_repo(repo_url: str, dest: Path, ref: str | None = None) -> None:
    """Clone a git repository into ``dest``.

    If ``ref`` is a 40-char hex SHA, a full clone is performed and the ref is
    checked out. Otherwise a shallow clone of the branch/tag is performed.
    """
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)

    try:
        if ref and _is_sha(ref):
            subprocess.run(
                ["git", "clone", repo_url, str(dest)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(dest), "checkout", ref],
                check=True,
                capture_output=True,
                text=True,
            )
        elif ref:
            subprocess.run(
                ["git", "clone", "--branch", ref, "--depth", "1", repo_url, str(dest)],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(dest)],
                check=True,
                capture_output=True,
                text=True,
            )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr or ""
        raise GitError(f"Failed to clone {repo_url}: {stderr}") from exc


def get_commit_sha(repo_dir: Path) -> str:
    """Return the current HEAD commit SHA of the repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise GitError(f"Failed to get commit SHA: {exc.stderr}") from exc
    return result.stdout.strip()


def get_metadata_path(repo_dir: Path) -> Path:
    """Return the expected path of metadata.yaml inside a repo."""
    return repo_dir / "metadata.yaml"


@contextmanager
def temp_repo_dir() -> Generator[Path, None, None]:
    """Context manager yielding a temporary directory for cloning."""
    with TemporaryDirectory(prefix="astrbot-repo-") as tmp:
        yield Path(tmp)
