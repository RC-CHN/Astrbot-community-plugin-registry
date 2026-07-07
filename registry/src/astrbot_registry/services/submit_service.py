"""Repository submission workflow."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.build_service import build_from_repo
from ..services.plugin_service import (
    assert_metadata_matches_plugin,
    create_plugin,
    get_plugin_by_key,
    get_version_by_plugin_and_number,
)
from ..services.runtime_config import runtime_git_allowed_hosts, runtime_git_clone_timeout, runtime_git_http_proxy
from ..utils.git_utils import clone_repo, get_metadata_path, temp_repo_dir
from ..utils.metadata_parser import infer_plugin_key, parse_metadata_yaml
from .errors import ConflictError


async def submit_repo(
    db: AsyncSession,
    *,
    repo_url: str,
    version: str | None = None,
    ref: str | None = None,
    user_id: str | None = None,
) -> None:
    git_clone_timeout = await runtime_git_clone_timeout(db)
    git_allowed_hosts = await runtime_git_allowed_hosts(db)
    git_http_proxy = await runtime_git_http_proxy(db)
    with temp_repo_dir() as repo_dir:
        clone_repo(
            repo_url,
            repo_dir,
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
            repo_url,
            created_by=uuid.UUID(user_id) if user_id else None,
        )
    else:
        assert_metadata_matches_plugin(metadata, plugin)

    version_str = version or metadata.version
    if await get_version_by_plugin_and_number(db, plugin.id, version_str):
        raise ConflictError(f"Version {version_str} already exists for plugin {plugin.plugin_key}")

    await build_from_repo(db, plugin, version_str, ref=ref, created_by=user_id)
