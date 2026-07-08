"""Git provider registry."""

from __future__ import annotations

from urllib.parse import urlparse

from ...config import settings
from ...utils.git_utils import GitError
from .base import GitCredential, GitProvider, NormalizedRepo
from .github import GitHubProvider

_PROVIDERS: dict[str, GitProvider] = {
    "github": GitHubProvider(),
}

_HOST_PROVIDER = {
    "github.com": "github",
}


def get_git_provider(provider: str) -> GitProvider:
    try:
        return _PROVIDERS[provider]
    except KeyError as exc:
        raise GitError(f"Unsupported Git provider: {provider}") from exc


def get_git_provider_for_url(repo_url: str, *, allowed_hosts: list[str] | None = None) -> GitProvider:
    host = (urlparse(repo_url).hostname or "").lower()
    allowed_hosts = allowed_hosts or settings.git_allowed_hosts
    if host not in allowed_hosts:
        raise ValueError(f"Git host is not allowed: {host}")
    provider_name = _HOST_PROVIDER.get(host)
    if provider_name is None:
        raise GitError(f"No Git provider is configured for host: {host}")
    return get_git_provider(provider_name)


__all__ = [
    "GitCredential",
    "GitProvider",
    "NormalizedRepo",
    "get_git_provider",
    "get_git_provider_for_url",
]
