"""GitHub clone, zip packaging, and S3 upload."""

import zipfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Plugin, PluginVersion
from ..services.plugin_service import update_version_after_build
from ..services.s3_service import build_public_url, build_s3_key, upload_file
from ..utils.git_utils import clone_repo, get_commit_sha, get_metadata_path, temp_repo_dir
from ..utils.metadata_parser import PluginMetadata, parse_metadata_yaml


def _should_skip(rel: Path) -> bool:
    parts = rel.parts
    if ".git" in parts:
        return True
    if "__pycache__" in parts:
        return True
    if ".DS_Store" in parts or rel.name == ".DS_Store":
        return True
    if rel.name.endswith(".pyc"):
        return True
    if rel.name == ".python-version":
        return True
    return False


def _create_zip(repo_dir: Path, plugin_key: str, version: str) -> Path:
    zip_path = repo_dir.parent / f"{plugin_key}-{version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in repo_dir.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(repo_dir)
            if _should_skip(rel):
                continue
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

    # Create a pending version record to track the build.
    placeholder_key = build_s3_key(plugin, version, "git_auto", ref)
    pv = await create_version(
        db=db,
        plugin=plugin,
        version=version,
        metadata=PluginMetadata(name=plugin.plugin_key, author=plugin.author, version=version),
        s3_key=placeholder_key,
        download_url=build_public_url(placeholder_key),
        file_size=0,
        source_type="git_auto",
        commit_sha=ref,
        changelog="",
        created_by=uuid.UUID(created_by) if created_by else None,
        build_status="building",
    )

    try:
        with temp_repo_dir() as repo_dir:
            clone_repo(plugin.repo_url, repo_dir, ref=ref)
            metadata = parse_metadata_yaml(get_metadata_path(repo_dir))
            commit_sha = get_commit_sha(repo_dir)
            zip_path = _create_zip(repo_dir, plugin.plugin_key, version)
            s3_key = build_s3_key(plugin, version, "git_auto", commit_sha)
            await upload_file(zip_path, s3_key)
            await update_version_after_build(
                db=db,
                version=pv,
                metadata=metadata,
                s3_key=s3_key,
                download_url=build_public_url(s3_key),
                file_size=zip_path.stat().st_size,
                commit_sha=commit_sha,
            )
    except Exception as exc:
        pv.build_status = "failed"
        pv.build_log = str(exc)
        await db.commit()
        raise

    return pv
