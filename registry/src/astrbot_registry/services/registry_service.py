"""Registry JSON generation and caching."""

import hashlib
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..cache import get_redis
from ..models import Plugin, PluginVersion, PluginVersionStat
from ..services.plugin_service import scan_passed
from ..services.runtime_config import runtime_redis_cache_ttl, runtime_s3_public_url
from ..services.scan_service import public_sec_scan

CACHE_KEY = "registry_json"
MD5_KEY = "registry_md5"


async def generate_registry_json(db: AsyncSession) -> dict[str, Any]:
    """Generate the full registry JSON in the official AstrBot format."""
    client = await get_redis()
    if client:
        cached = await client.get(CACHE_KEY)
        if cached:
            return json.loads(cached if isinstance(cached, str) else cached.decode())

    plugins = await _fetch_active_plugins(db)
    s3_public_url = await runtime_s3_public_url(db)
    registry = {}
    for plugin in plugins:
        latest = _get_latest(plugin.versions)
        if latest is None:
            continue
        registry[plugin.plugin_key] = _format_entry(plugin, latest, s3_public_url=s3_public_url)

    if client:
        await client.set(CACHE_KEY, canonical_registry_json(registry), ex=await runtime_redis_cache_ttl(db))

    return registry


async def get_registry_md5(db: AsyncSession) -> str:
    """Return an MD5 checksum of the registry JSON."""
    redis = await get_redis()
    if redis:
        cached = await redis.get(MD5_KEY)
        if cached:
            return cached

    registry = await generate_registry_json(db)
    md5 = hashlib.md5(canonical_registry_bytes(registry)).hexdigest()

    if redis:
        await redis.set(MD5_KEY, md5, ex=await runtime_redis_cache_ttl(db))

    return md5


def canonical_registry_json(registry: dict[str, Any]) -> str:
    return json.dumps(
        registry,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_registry_bytes(registry: dict[str, Any]) -> bytes:
    return canonical_registry_json(registry).encode("utf-8")


async def refresh_cache(db: AsyncSession) -> None:
    """Invalidate the registry cache and regenerate it."""
    redis = await get_redis()
    if redis:
        await redis.delete(CACHE_KEY, MD5_KEY)
    await generate_registry_json(db)
    await get_registry_md5(db)


async def get_stats(db: AsyncSession) -> dict[str, Any]:
    """Return public-facing registry statistics."""
    total_plugins = await db.scalar(select(func.count(Plugin.id)).where(Plugin.status == "active"))
    total_versions = await db.scalar(
        select(func.count(PluginVersion.id))
        .join(Plugin)
        .where(Plugin.status == "active")
        .where(PluginVersion.version_status == "active")
    )
    total_downloads = await db.scalar(select(func.coalesce(func.sum(PluginVersionStat.download_count), 0)))
    total_installs = await db.scalar(select(func.coalesce(func.sum(PluginVersionStat.install_count), 0)))
    return {
        "total_plugins": total_plugins or 0,
        "total_active_versions": total_versions or 0,
        "total_downloads": total_downloads or 0,
        "total_installs": total_installs or 0,
    }


def _get_latest(versions: list[PluginVersion]) -> PluginVersion | None:
    for version in versions:
        if (
            version.is_latest
            and version.version_status == "active"
            and version.build_status == "success"
            and scan_passed(version)
        ):
            return version
    return None


def _format_entry(plugin: Plugin, version: PluginVersion, s3_public_url: str | None = None) -> dict[str, Any]:
    tags = [t.name for t in plugin.tags]
    return {
        "name": plugin.plugin_key,
        "display_name": plugin.display_name,
        "desc": plugin.description,
        "short_desc": "",
        "author": plugin.author,
        "repo": plugin.repo_url,
        "tags": tags,
        "tag": tags,
        "social_link": plugin.social_link,
        "stars": plugin.stars,
        "pinned": bool(plugin.pinned),
        "version": version.version,
        "updated_at": version.created_at.isoformat() if version.created_at else "",
        "logo": _logo_url(plugin.logo_s3_key, s3_public_url=s3_public_url),
        "commit_sha": version.commit_sha,
        "download_url": version.download_url or "",
        "sec_scan": public_sec_scan(version, coerce_unknown_to_false=True),
        "i18n": {i.locale: i.data for i in plugin.i18n_entries},
        "astrbot_version": plugin.astrbot_version,
        "support_platforms": plugin.support_platforms or [],
        "category": plugin.category,
    }


def _logo_url(logo_s3_key: str | None, s3_public_url: str | None = None) -> str:
    if not logo_s3_key:
        return ""
    from ..config import settings

    public_url = s3_public_url or settings.s3_public_url
    return f"{public_url.rstrip('/')}/{logo_s3_key.lstrip('/')}"


async def _fetch_active_plugins(db: AsyncSession) -> list[Plugin]:
    result = await db.execute(
        select(Plugin)
        .where(Plugin.status == "active")
        .options(
            selectinload(Plugin.tags),
            selectinload(Plugin.i18n_entries),
            selectinload(Plugin.versions).selectinload(PluginVersion.scan),
            selectinload(Plugin.versions).selectinload(PluginVersion.provider_results),
        )
    )
    return list(result.scalars().unique().all())
