"""Provider abstractions for Git hosting services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class GitCredential:
    """Runtime credential selected for a Git operation.

    ``temporary_token`` is used for the current request only. Future persistent
    credentials can resolve ``credential_id`` to a decrypted token without
    changing provider call sites.
    """

    temporary_token: str | None = None
    credential_id: str | None = None


@dataclass(frozen=True)
class NormalizedRepo:
    provider: str
    repo_url: str
    owner: str
    repo: str
    host: str
    detected_ref_type: str | None = None
    detected_ref: str | None = None


class GitProvider(Protocol):
    name: str

    def normalize_url(self, repo_url: str, *, allowed_hosts: list[str] | None = None) -> NormalizedRepo:
        """Normalize a user-entered URL and detect embedded refs if present."""

    def inspect_repo(
        self,
        repo: NormalizedRepo,
        *,
        credential: GitCredential,
        ref_type: str | None,
        ref: str | None,
        include_refs: bool,
        proxy_url: str | None,
        timeout: int | None,
    ) -> dict[str, Any]:
        """Return repository metadata, refs, selected commit, and metadata.yaml preview."""

    def resolve_ref(
        self,
        repo: NormalizedRepo,
        *,
        credential: GitCredential,
        ref_type: str | None,
        ref: str | None,
        proxy_url: str | None,
        timeout: int | None,
    ) -> dict[str, Any]:
        """Return the selected commit and metadata.yaml preview for one ref."""

    def preflight_repo_size(
        self,
        repo_url: str,
        *,
        credential: GitCredential,
        max_size_kb: int,
        timeout: int | None,
        allowed_hosts: list[str] | None,
        proxy_url: str | None,
    ) -> int | None:
        """Validate repository size before clone."""

    def clone_repo(
        self,
        repo_url: str,
        dest: Path,
        *,
        credential: GitCredential,
        ref: str | None,
        timeout: int | None,
        allowed_hosts: list[str] | None,
        proxy_url: str | None,
    ) -> None:
        """Clone the repository into ``dest``."""
