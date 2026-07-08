"""Repository inspection workflow used by admin import UI."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PluginVersion
from .git_providers import GitCredential, get_git_provider_for_url
from .plugin_service import get_plugin_by_key, get_version_by_plugin_and_commit
from .runtime_config import runtime_github_token


async def inspect_git_repo(
    db: AsyncSession,
    *,
    repo_url: str,
    temporary_token: str | None = None,
    credential_id: str | None = None,
    ref_type: str | None = None,
    ref: str | None = None,
    include_refs: bool = True,
    allowed_hosts: list[str] | None = None,
    proxy_url: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    provider = get_git_provider_for_url(repo_url, allowed_hosts=allowed_hosts)
    normalized = provider.normalize_url(repo_url, allowed_hosts=allowed_hosts)
    effective_token = temporary_token or await runtime_github_token(db)
    credential = GitCredential(
        temporary_token=effective_token,
        credential_id=credential_id,
    )
    raw = await asyncio.to_thread(
        provider.inspect_repo,
        normalized,
        credential=credential,
        ref_type=ref_type,
        ref=ref,
        include_refs=include_refs,
        proxy_url=proxy_url,
        timeout=timeout,
    )
    raw["match"] = await _match_repo_metadata(db, raw["metadata"], raw["selected_commit"]["sha"])
    return raw


async def resolve_git_ref(
    db: AsyncSession,
    *,
    repo_url: str,
    temporary_token: str | None = None,
    credential_id: str | None = None,
    ref_type: str | None = None,
    ref: str | None = None,
    allowed_hosts: list[str] | None = None,
    proxy_url: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    provider = get_git_provider_for_url(repo_url, allowed_hosts=allowed_hosts)
    normalized = provider.normalize_url(repo_url, allowed_hosts=allowed_hosts)
    effective_token = temporary_token or await runtime_github_token(db)
    credential = GitCredential(
        temporary_token=effective_token,
        credential_id=credential_id,
    )
    raw = await asyncio.to_thread(
        provider.resolve_ref,
        normalized,
        credential=credential,
        ref_type=ref_type,
        ref=ref,
        proxy_url=proxy_url,
        timeout=timeout,
    )
    raw["match"] = await _match_repo_metadata(db, raw["metadata"], raw["selected_commit"]["sha"])
    return raw


async def _match_repo_metadata(
    db: AsyncSession,
    metadata: dict[str, Any],
    commit_sha: str,
) -> dict[str, Any]:
    plugin = await get_plugin_by_key(db, metadata["plugin_key"])
    duplicate_version_count = 0
    duplicate_commit_version_id = None
    match_status = "new_plugin"
    if plugin is not None:
        match_status = "new_commit"
        duplicate_version_count = await db.scalar(
            select(func.count(PluginVersion.id)).where(
                PluginVersion.plugin_id == plugin.id,
                PluginVersion.version == metadata["version"],
            )
        ) or 0
        existing_commit = await get_version_by_plugin_and_commit(
            db,
            plugin.id,
            commit_sha,
        )
        if existing_commit is not None:
            match_status = "duplicate_commit"
            duplicate_commit_version_id = str(existing_commit.id)

    return {
        "status": match_status,
        "plugin_id": str(plugin.id) if plugin is not None else None,
        "plugin_key": plugin.plugin_key if plugin is not None else metadata["plugin_key"],
        "duplicate_version_count": duplicate_version_count,
        "duplicate_commit_version_id": duplicate_commit_version_id,
    }
