"""GitHub clone, zip packaging, and S3 upload."""

import zipfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Plugin, PluginVersion
from ..services.errors import InvalidStateError, ValidationError
from ..services.plugin_service import assert_metadata_matches_plugin, update_version_after_build
from ..services.runtime_config import (
    runtime_git_allowed_hosts,
    runtime_git_clone_timeout,
    runtime_max_release_zip_bytes,
    runtime_s3_layout,
    runtime_s3_public_url,
)
from ..services.s3_service import build_public_url_with_base, build_s3_key_with_layout, upload_file
from ..services.scan_service import scan_version
from ..utils.git_utils import clone_repo, get_commit_sha, get_metadata_path, temp_repo_dir
from ..utils.metadata_parser import PluginMetadata, parse_metadata_yaml


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
    version: str,
    ref: str | None = None,
    created_by: str | None = None,
) -> PluginVersion:
    """Clone a GitHub repo, build a zip, upload to S3, and create a version record."""
    import uuid

    from ..services.plugin_service import create_version

    if not plugin.repo_url:
        raise InvalidStateError("Plugin has no repository URL")

    s3_layout = await runtime_s3_layout(db)
    s3_public_url = await runtime_s3_public_url(db)
    git_clone_timeout = await runtime_git_clone_timeout(db)
    git_allowed_hosts = await runtime_git_allowed_hosts(db)
    max_release_zip_bytes = await runtime_max_release_zip_bytes(db)

    # Create a pending version record to track the build.
    placeholder_key = build_s3_key_with_layout(plugin, version, "git_auto", ref, **s3_layout)
    pv = await create_version(
        db=db,
        plugin=plugin,
        version=version,
        metadata=PluginMetadata(name=plugin.plugin_key, author=plugin.author, version=version),
        s3_key=placeholder_key,
        download_url=build_public_url_with_base(placeholder_key, s3_public_url),
        file_size=0,
        source_type="git_auto",
        commit_sha=ref,
        changelog="",
        created_by=uuid.UUID(created_by) if created_by else None,
        build_status="building",
    )

    try:
        with temp_repo_dir() as repo_dir:
            clone_repo(
                plugin.repo_url,
                repo_dir,
                ref=ref,
                timeout=git_clone_timeout,
                allowed_hosts=git_allowed_hosts,
            )
            metadata = parse_metadata_yaml(get_metadata_path(repo_dir))
            assert_metadata_matches_plugin(metadata, plugin)
            commit_sha = get_commit_sha(repo_dir)
            zip_path = _create_zip(repo_dir, plugin.plugin_key, version, max_release_zip_bytes)
            s3_key = build_s3_key_with_layout(plugin, version, "git_auto", commit_sha, **s3_layout)
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
        pv.build_status = "failed"
        pv.build_log = str(exc)
        await db.commit()
        raise

    return pv
