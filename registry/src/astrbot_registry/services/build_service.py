"""GitHub clone, zip packaging, and S3 upload."""

import zipfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Plugin, PluginVersion
from ..services.errors import ConflictError, InvalidStateError, ValidationError
from ..services.git_providers import GitCredential, get_git_provider_for_url
from ..services.plugin_service import (
    assert_metadata_matches_plugin,
    get_version_by_plugin_and_commit,
    update_version_after_build,
)
from ..services.runtime_config import (
    runtime_git_allowed_hosts,
    runtime_git_clone_timeout,
    runtime_git_http_proxy,
    runtime_git_max_repo_size_kb,
    runtime_git_preflight_timeout,
    runtime_github_token,
    runtime_max_release_zip_bytes,
    runtime_s3_layout,
    runtime_s3_public_url,
)
from ..services.s3_service import build_public_url_with_base, build_s3_key_with_layout, upload_file
from ..services.scan_service import scan_version
from ..utils.git_utils import (
    get_commit_sha,
    get_metadata_path,
    temp_repo_dir,
)
from ..utils.metadata_parser import PluginMetadata, overwrite_metadata_version, parse_metadata_yaml


def _should_skip(rel: Path) -> bool:
    parts = rel.parts
    if ".git" in parts:
        return True
    if "__pycache__" in parts:
        return True
    if "node_modules" in parts:
        return True
    if ".venv" in parts or "venv" in parts:
        return True
    if "dist" in parts or "build" in parts:
        return True
    if ".DS_Store" in parts or rel.name == ".DS_Store":
        return True
    if rel.name in {".env", ".env.local"}:
        return True
    if rel.name.endswith(".pyc"):
        return True
    if rel.name == ".python-version":
        return True
    return False


def _create_zip(repo_dir: Path, plugin_key: str, version: str, max_release_zip_bytes: int) -> Path:
    zip_path = repo_dir.parent / f"{plugin_key}-{version}.zip"
    total_size = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in repo_dir.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(repo_dir)
            if _should_skip(rel):
                continue
            total_size += file_path.stat().st_size
            if total_size > max_release_zip_bytes:
                raise ValidationError("release zip is too large")
            zf.write(file_path, rel)
    return zip_path


async def build_from_repo(
    db: AsyncSession,
    plugin: Plugin,
    version: str | None,
    ref: str | None = None,
    credential_id: str | None = None,
    temporary_token: str | None = None,
    changelog: str = "",
    created_by: str | None = None,
) -> PluginVersion:
    """Clone a Git repo, build a zip, upload to S3, and create a version record."""
    import uuid

    from ..services.plugin_service import create_version

    if not plugin.repo_url:
        raise InvalidStateError("Plugin has no repository URL")

    s3_layout = await runtime_s3_layout(db)
    s3_public_url = await runtime_s3_public_url(db)
    git_clone_timeout = await runtime_git_clone_timeout(db)
    git_preflight_timeout = await runtime_git_preflight_timeout(db)
    git_max_repo_size_kb = await runtime_git_max_repo_size_kb(db)
    git_allowed_hosts = await runtime_git_allowed_hosts(db)
    git_http_proxy = await runtime_git_http_proxy(db)
    effective_token = temporary_token or await runtime_github_token(db)
    max_release_zip_bytes = await runtime_max_release_zip_bytes(db)
    provider = get_git_provider_for_url(plugin.repo_url, allowed_hosts=git_allowed_hosts)
    credential = GitCredential(temporary_token=effective_token, credential_id=credential_id)

    pv: PluginVersion | None = None
    try:
        provider.preflight_repo_size(
            plugin.repo_url,
            credential=credential,
            max_size_kb=git_max_repo_size_kb,
            timeout=git_preflight_timeout,
            allowed_hosts=git_allowed_hosts,
            proxy_url=git_http_proxy,
        )
        with temp_repo_dir() as repo_dir:
            provider.clone_repo(
                plugin.repo_url,
                repo_dir,
                credential=credential,
                ref=ref,
                timeout=git_clone_timeout,
                allowed_hosts=git_allowed_hosts,
                proxy_url=git_http_proxy,
            )
            metadata_path = get_metadata_path(repo_dir)
            metadata = parse_metadata_yaml(metadata_path)
            effective_version = version or metadata.version
            if version is not None and metadata.version != version:
                overwrite_metadata_version(metadata_path, version)
                metadata = parse_metadata_yaml(metadata_path)
            assert_metadata_matches_plugin(metadata, plugin)
            commit_sha = get_commit_sha(repo_dir)
            existing = await get_version_by_plugin_and_commit(db, plugin.id, commit_sha)
            if existing is not None:
                raise ConflictError(
                    f"Commit {commit_sha[:12]} already exists for plugin {plugin.plugin_key}"
                )

            placeholder_key = build_s3_key_with_layout(
                plugin, effective_version, "git_auto", None, **s3_layout
            )
            pv = await create_version(
                db=db,
                plugin=plugin,
                version=effective_version,
                metadata=PluginMetadata(
                    name=plugin.plugin_key,
                    author=plugin.author,
                    version=effective_version,
                ),
                s3_key=placeholder_key,
                download_url=build_public_url_with_base(placeholder_key, s3_public_url),
                file_size=0,
                source_type="git_auto",
                commit_sha=None,
                source_ref=ref,
                changelog=changelog,
                created_by=uuid.UUID(created_by) if created_by else None,
                build_status="building",
            )

            zip_path = _create_zip(repo_dir, plugin.plugin_key, effective_version, max_release_zip_bytes)
            s3_key = build_s3_key_with_layout(
                plugin, effective_version, "git_auto", commit_sha, **s3_layout
            )
            await upload_file(zip_path, s3_key)
            await update_version_after_build(
                db=db,
                version=pv,
                metadata=metadata,
                s3_key=s3_key,
                download_url=build_public_url_with_base(s3_key, s3_public_url),
                file_size=zip_path.stat().st_size,
                commit_sha=commit_sha,
            )
            await scan_version(db, pv.id, local_path=zip_path)
    except Exception as exc:
        if pv is not None:
            pv.build_status = "failed"
            pv.build_log = str(exc)
            await db.commit()
        raise

    if pv is None:
        raise InvalidStateError("Build did not create a version")
    return pv
