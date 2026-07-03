"""Plugin and version CRUD services."""

import uuid
from pathlib import Path
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Plugin, PluginI18n, PluginVersion, Tag
from ..schemas.plugin import PluginUpdate
from ..services.s3_service import build_public_url, build_s3_key, upload_file
from ..utils.metadata_parser import PluginMetadata, infer_plugin_key


async def get_plugin(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin | None:
    return await db.get(Plugin, plugin_id)


async def get_plugin_by_key(db: AsyncSession, plugin_key: str) -> Plugin | None:
    result = await db.execute(select(Plugin).where(Plugin.plugin_key == plugin_key))
    return result.scalar_one_or_none()


async def get_version(db: AsyncSession, version_id: uuid.UUID) -> PluginVersion | None:
    return await db.get(PluginVersion, version_id)


async def get_latest_version(db: AsyncSession, plugin_id: uuid.UUID) -> PluginVersion | None:
    result = await db.execute(
        select(PluginVersion)
        .where(PluginVersion.plugin_id == plugin_id)
        .where(PluginVersion.is_latest.is_(True))
        .where(PluginVersion.version_status == "active")
    )
    return result.scalar_one_or_none()


async def create_plugin(
    db: AsyncSession,
    metadata: PluginMetadata,
    repo_url: str,
    created_by: uuid.UUID | None = None,
) -> Plugin:
    plugin_key = infer_plugin_key(metadata.name)
    existing = await get_plugin_by_key(db, plugin_key)
    if existing is not None:
        raise ValueError(f"Plugin key already exists: {plugin_key}")

    plugin = Plugin(
        plugin_key=plugin_key,
        display_name=metadata.display_name,
        description=metadata.desc,
        author=metadata.author,
        repo_url=repo_url or metadata.repo or "",
        social_link=metadata.social_link,
        category=metadata.category,
        support_platforms=metadata.support_platforms,
        astrbot_version=metadata.astrbot_version,
        status="pending",
        created_by=created_by,
    )
    db.add(plugin)
    await db.flush()
    await db.refresh(plugin)

    if metadata.tags:
        tags = await _ensure_tags(db, metadata.tags)
        plugin.tags = tags

    if metadata.i18n:
        for locale, data in metadata.i18n.items():
            db.add(PluginI18n(plugin_id=plugin.id, locale=locale, data=data))

    await db.commit()
    await db.refresh(plugin)
    return plugin


async def update_plugin(
    db: AsyncSession,
    plugin: Plugin,
    data: PluginUpdate,
) -> Plugin:
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "tags":
            if value is not None:
                plugin.tags = await _ensure_tags(db, value)
        elif hasattr(plugin, field):
            setattr(plugin, field, value)

    await db.commit()
    await db.refresh(plugin)
    return plugin


async def set_plugin_status(
    db: AsyncSession,
    plugin_id: uuid.UUID,
    status: str,
) -> Plugin:
    plugin = await get_plugin(db, plugin_id)
    if plugin is None:
        raise ValueError("Plugin not found")
    plugin.status = status
    await db.commit()
    await db.refresh(plugin)
    return plugin


async def delete_plugin(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin:
    plugin = await get_plugin(db, plugin_id)
    if plugin is None:
        raise ValueError("Plugin not found")
    plugin.status = "deleted"
    await db.commit()
    await db.refresh(plugin)
    return plugin


async def create_version(
    db: AsyncSession,
    plugin: Plugin,
    version: str,
    metadata: PluginMetadata,
    s3_key: str,
    download_url: str,
    file_size: int,
    source_type: str,
    commit_sha: str | None = None,
    changelog: str = "",
    created_by: uuid.UUID | None = None,
    build_status: str = "pending",
) -> PluginVersion:
    existing = await db.execute(
        select(PluginVersion)
        .where(PluginVersion.plugin_id == plugin.id)
        .where(PluginVersion.version == version)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Version {version} already exists for plugin {plugin.plugin_key}")

    pv = PluginVersion(
        plugin_id=plugin.id,
        version=version,
        commit_sha=commit_sha,
        source_type=source_type,
        s3_key=s3_key,
        download_url=download_url,
        file_size=file_size,
        metadata_raw=metadata.model_dump_json(),
        changelog=changelog,
        build_status=build_status,
        version_status="draft",
        is_latest=False,
        created_by=created_by,
    )
    db.add(pv)
    await db.commit()
    await db.refresh(pv)
    return pv


async def update_version_after_build(
    db: AsyncSession,
    version: PluginVersion,
    metadata: PluginMetadata,
    s3_key: str,
    download_url: str,
    file_size: int,
    commit_sha: str | None,
) -> PluginVersion:
    version.s3_key = s3_key
    version.download_url = download_url
    version.file_size = file_size
    version.metadata_raw = metadata.model_dump_json()
    version.commit_sha = commit_sha
    version.build_status = "success"
    await db.commit()
    await db.refresh(version)
    return version


async def set_version_status(
    db: AsyncSession,
    version_id: uuid.UUID,
    status: str,
) -> PluginVersion:
    version = await get_version(db, version_id)
    if version is None:
        raise ValueError("Version not found")
    version.version_status = status
    await db.commit()
    await db.refresh(version)
    return version


async def set_latest_version(
    db: AsyncSession,
    plugin_id: uuid.UUID,
    version_id: uuid.UUID,
) -> PluginVersion:
    version = await get_version(db, version_id)
    if version is None or version.plugin_id != plugin_id:
        raise ValueError("Version not found")
    if version.version_status != "active":
        raise ValueError("Version must be active to be set as latest")

    await db.execute(
        update(PluginVersion)
        .where(PluginVersion.plugin_id == plugin_id)
        .values(is_latest=False)
    )
    version.is_latest = True
    await db.commit()
    await db.refresh(version)
    return version


async def list_versions(
    db: AsyncSession,
    plugin_id: uuid.UUID,
) -> Sequence[PluginVersion]:
    result = await db.execute(
        select(PluginVersion)
        .where(PluginVersion.plugin_id == plugin_id)
        .order_by(PluginVersion.created_at.desc())
    )
    return result.scalars().all()


async def list_active_plugins_with_versions(
    db: AsyncSession,
) -> Sequence[Plugin]:
    result = await db.execute(
        select(Plugin)
        .where(Plugin.status == "active")
        .options(
            selectinload(Plugin.tags),
            selectinload(Plugin.i18n_entries),
            selectinload(Plugin.versions),
        )
    )
    return result.scalars().unique().all()


async def create_version_from_upload(
    db: AsyncSession,
    plugin: Plugin,
    metadata: PluginMetadata,
    zip_path: Path,
    version: str,
    changelog: str = "",
    created_by: uuid.UUID | None = None,
) -> PluginVersion:
    """Upload a manually provided zip and create a version record."""
    s3_key = build_s3_key(plugin, version, "manual_upload")
    await upload_file(zip_path, s3_key)
    return await create_version(
        db=db,
        plugin=plugin,
        version=version,
        metadata=metadata,
        s3_key=s3_key,
        download_url=build_public_url(s3_key),
        file_size=zip_path.stat().st_size,
        source_type="manual_upload",
        commit_sha=None,
        changelog=changelog,
        created_by=created_by,
        build_status="success",
    )


async def _ensure_tags(db: AsyncSession, names: Sequence[str]) -> Sequence[Tag]:
    names = [name.strip().lower() for name in names if name.strip()]
    if not names:
        return []

    result = await db.execute(select(Tag).where(Tag.name.in_(names)))
    existing = {tag.name: tag for tag in result.scalars().all()}

    tags: list[Tag] = []
    for name in names:
        if name in existing:
            tags.append(existing[name])
        else:
            tag = Tag(name=name)
            db.add(tag)
            tags.append(tag)

    await db.flush()
    return tags
