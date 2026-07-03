"""Plugin and version CRUD services."""

import uuid
from pathlib import Path
from typing import Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Plugin, PluginI18n, PluginVersion, Tag
from ..schemas.plugin import PluginUpdate
from ..services.errors import ConflictError, InvalidStateError, NotFoundError, ValidationError
from ..services.runtime_config import runtime_s3_layout, runtime_s3_public_url
from ..services.s3_service import build_public_url_with_base, build_s3_key_with_layout, upload_file
from ..utils.metadata_parser import PluginMetadata, infer_plugin_key


async def get_plugin(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin | None:
    return await db.get(Plugin, plugin_id)


async def get_plugin_by_key(db: AsyncSession, plugin_key: str) -> Plugin | None:
    result = await db.execute(select(Plugin).where(Plugin.plugin_key == plugin_key))
    return result.scalar_one_or_none()


async def get_plugin_with_details(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin | None:
    result = await db.execute(
        select(Plugin)
        .where(Plugin.id == plugin_id)
        .options(
            selectinload(Plugin.tags),
            selectinload(Plugin.i18n_entries),
            selectinload(Plugin.versions).selectinload(PluginVersion.scan),
        )
    )
    return result.scalar_one_or_none()


async def get_version(db: AsyncSession, version_id: uuid.UUID) -> PluginVersion | None:
    return await db.get(PluginVersion, version_id)


async def get_version_by_plugin_and_number(
    db: AsyncSession,
    plugin_id: uuid.UUID,
    version: str,
) -> PluginVersion | None:
    result = await db.execute(
        select(PluginVersion)
        .where(PluginVersion.plugin_id == plugin_id)
        .where(PluginVersion.version == version)
    )
    return result.scalar_one_or_none()


async def get_latest_version(db: AsyncSession, plugin_id: uuid.UUID) -> PluginVersion | None:
    result = await db.execute(
        select(PluginVersion)
        .where(PluginVersion.plugin_id == plugin_id)
        .where(PluginVersion.is_latest.is_(True))
        .where(PluginVersion.version_status == "active")
        .where(PluginVersion.build_status == "success")
        .options(selectinload(PluginVersion.scan))
    )
    version = result.scalar_one_or_none()
    if version is None or not scan_passed(version):
        return None
    return version


async def create_plugin(
    db: AsyncSession,
    metadata: PluginMetadata,
    repo_url: str,
    created_by: uuid.UUID | None = None,
) -> Plugin:
    plugin_key = infer_plugin_key(metadata.name)
    existing = await get_plugin_by_key(db, plugin_key)
    if existing is not None:
        raise ConflictError(f"Plugin key already exists: {plugin_key}")

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
    await _refresh_registry_cache(db)
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
    await _refresh_registry_cache(db)
    return plugin


async def set_plugin_status(
    db: AsyncSession,
    plugin_id: uuid.UUID,
    status: str,
    review_status: str | None = None,
) -> Plugin:
    plugin = await get_plugin(db, plugin_id)
    if plugin is None:
        raise NotFoundError("Plugin not found")
    plugin.status = status
    if review_status is not None:
        plugin.review_status = review_status
    elif status == "active" and plugin.review_status == "pending":
        plugin.review_status = "approved"
    elif status == "disabled" and plugin.review_status == "pending":
        plugin.review_status = "rejected"
    if status in {"disabled", "deleted"}:
        await db.execute(
            update(PluginVersion)
            .where(PluginVersion.plugin_id == plugin_id)
            .values(is_latest=False)
        )
    await db.commit()
    await db.refresh(plugin)
    await _refresh_registry_cache(db)
    return plugin


async def delete_plugin(db: AsyncSession, plugin_id: uuid.UUID) -> Plugin:
    plugin = await get_plugin(db, plugin_id)
    if plugin is None:
        raise NotFoundError("Plugin not found")
    await db.delete(plugin)
    await db.commit()
    await _refresh_registry_cache(db)
    return plugin


async def create_version(
    db: AsyncSession,
    plugin: Plugin,
    version: str,
    metadata: PluginMetadata,
    s3_key: str | None,
    download_url: str | None,
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
        raise ConflictError(f"Version {version} already exists for plugin {plugin.plugin_key}")

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
    await _refresh_registry_cache(db)
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
    await _refresh_registry_cache(db)
    return version


async def set_version_status(
    db: AsyncSession,
    version_id: uuid.UUID,
    status: str,
) -> PluginVersion:
    version = await get_version(db, version_id)
    if version is None:
        raise NotFoundError("Version not found")
    if status == "active":
        if version.build_status != "success":
            raise InvalidStateError("Version build must be successful before activation")
        result = await db.execute(
            select(PluginVersion)
            .where(PluginVersion.id == version_id)
            .options(selectinload(PluginVersion.scan))
        )
        version = result.scalar_one()
        if not scan_passed(version):
            raise InvalidStateError("Version security scan must pass before activation")
    version.version_status = status
    if status in {"draft", "deprecated", "deleted"}:
        version.is_latest = False
    await db.commit()
    await db.refresh(version)
    await _refresh_registry_cache(db)
    return version


async def set_latest_version(
    db: AsyncSession,
    plugin_id: uuid.UUID,
    version_id: uuid.UUID,
) -> PluginVersion:
    plugin = await db.scalar(
        select(Plugin)
        .where(Plugin.id == plugin_id)
        .with_for_update()
    )
    if plugin is None:
        raise NotFoundError("Plugin not found")
    if plugin.status != "active":
        raise InvalidStateError("Plugin must be active before setting latest")

    result = await db.execute(
        select(PluginVersion)
        .where(PluginVersion.plugin_id == plugin_id)
        .options(selectinload(PluginVersion.scan))
        .with_for_update()
    )
    versions = result.scalars().all()
    version = next((item for item in versions if item.id == version_id), None)
    if version is None:
        raise NotFoundError("Version not found")
    if version.version_status != "active":
        raise InvalidStateError("Version must be active to be set as latest")
    if version.build_status != "success":
        raise InvalidStateError("Version build must be successful to be set as latest")
    if not scan_passed(version):
        raise InvalidStateError("Version security scan must pass before setting latest")

    await db.execute(
        update(PluginVersion)
        .where(PluginVersion.plugin_id == plugin_id)
        .values(is_latest=False)
    )
    version.is_latest = True
    await db.commit()
    await db.refresh(version)
    await _refresh_registry_cache(db)
    return version


async def list_versions(
    db: AsyncSession,
    plugin_id: uuid.UUID,
) -> Sequence[PluginVersion]:
    result = await db.execute(
        select(PluginVersion)
        .where(PluginVersion.plugin_id == plugin_id)
        .options(selectinload(PluginVersion.scan))
        .order_by(PluginVersion.created_at.desc())
    )
    return result.scalars().all()


async def list_plugins(
    db: AsyncSession,
    *,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[Sequence[Plugin], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    filters = []
    if status:
        filters.append(Plugin.status == status)
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Plugin.plugin_key.ilike(like),
                Plugin.display_name.ilike(like),
                Plugin.description.ilike(like),
                Plugin.author.ilike(like),
            )
        )

    base = select(Plugin).where(*filters)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    result = await db.execute(
        base.options(selectinload(Plugin.tags), selectinload(Plugin.versions))
        .order_by(Plugin.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return result.scalars().unique().all(), total or 0


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
    assert_metadata_matches_plugin(metadata, plugin)
    s3_layout = await runtime_s3_layout(db)
    s3_public_url = await runtime_s3_public_url(db)
    s3_key = build_s3_key_with_layout(plugin, version, "manual_upload", **s3_layout)
    await upload_file(zip_path, s3_key)
    return await create_version(
        db=db,
        plugin=plugin,
        version=version,
        metadata=metadata,
        s3_key=s3_key,
        download_url=build_public_url_with_base(s3_key, s3_public_url),
        file_size=zip_path.stat().st_size,
        source_type="manual_upload",
        commit_sha=None,
        changelog=changelog,
        created_by=created_by,
        build_status="success",
    )


def scan_passed(version: PluginVersion) -> bool:
    scan = version.scan
    if scan is None:
        return False
    return bool(scan.virustotal_pass) and bool(scan.llm_agent_pass)


def assert_metadata_matches_plugin(metadata: PluginMetadata, plugin: Plugin) -> None:
    expected_key = plugin.plugin_key
    actual_key = infer_plugin_key(metadata.name)
    if actual_key != expected_key:
        raise ValidationError(
            f"metadata plugin key {actual_key} does not match existing plugin {expected_key}"
        )
    if metadata.author != plugin.author:
        raise ValidationError("metadata author does not match existing plugin")


async def _refresh_registry_cache(db: AsyncSession) -> None:
    from ..services.registry_service import refresh_cache

    await refresh_cache(db)


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
