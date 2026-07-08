"""Repository submission workflow."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.build_service import build_from_repo
from ..services.git_providers import GitCredential, get_git_provider_for_url
from ..services.plugin_service import (
    assert_metadata_matches_plugin,
    create_plugin,
    get_plugin_by_key,
)
from ..services.runtime_config import (
    runtime_git_allowed_hosts,
    runtime_git_clone_timeout,
    runtime_git_http_proxy,
    runtime_git_max_repo_size_kb,
    runtime_git_preflight_timeout,
    runtime_github_token,
)
from ..utils.git_utils import get_metadata_path, temp_repo_dir
from ..utils.metadata_parser import infer_plugin_key, parse_metadata_yaml


async def submit_repo(
    db: AsyncSession,
    *,
    repo_url: str,
    version: str | None = None,
    ref: str | None = None,
    credential_id: str | None = None,
    temporary_token: str | None = None,
    changelog: str = "",
    user_id: str | None = None,
) -> None:
    git_clone_timeout = await runtime_git_clone_timeout(db)
    git_preflight_timeout = await runtime_git_preflight_timeout(db)
    git_max_repo_size_kb = await runtime_git_max_repo_size_kb(db)
    git_allowed_hosts = await runtime_git_allowed_hosts(db)
    git_http_proxy = await runtime_git_http_proxy(db)
    effective_token = temporary_token or await runtime_github_token(db)
    provider = get_git_provider_for_url(repo_url, allowed_hosts=git_allowed_hosts)
    credential = GitCredential(temporary_token=effective_token, credential_id=credential_id)
    preflight_url = provider.normalize_url(repo_url, allowed_hosts=git_allowed_hosts).repo_url
    provider.preflight_repo_size(
        preflight_url,
        credential=credential,
        max_size_kb=git_max_repo_size_kb,
        timeout=git_preflight_timeout,
        allowed_hosts=git_allowed_hosts,
        proxy_url=git_http_proxy,
    )
    with temp_repo_dir() as repo_dir:
        provider.clone_repo(
            preflight_url,
            repo_dir,
            credential=credential,
            ref=ref,
            timeout=git_clone_timeout,
            allowed_hosts=git_allowed_hosts,
            proxy_url=git_http_proxy,
        )
        metadata = parse_metadata_yaml(get_metadata_path(repo_dir))

    plugin = await get_plugin_by_key(db, infer_plugin_key(metadata.name))
    if plugin is None:
        plugin = await create_plugin(
            db,
            metadata,
            preflight_url,
            created_by=uuid.UUID(user_id) if user_id else None,
        )
    else:
        assert_metadata_matches_plugin(metadata, plugin)

    version_str = version or metadata.version
    await build_from_repo(
        db,
        plugin,
        version_str,
        ref=ref,
        credential_id=credential_id,
        temporary_token=temporary_token,
        changelog=changelog,
        created_by=user_id,
    )
