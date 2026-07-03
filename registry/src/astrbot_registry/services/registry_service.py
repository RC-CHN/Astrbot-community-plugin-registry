"""Registry JSON generation and caching."""

import hashlib
import json
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..cache import get_redis
from ..config import settings
from ..models import Plugin, PluginVersion
from ..services.plugin_service import scan_passed

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
    registry = {}
    for plugin in plugins:
        latest = _get_latest(plugin.versions)
        if latest is None:
            continue
        registry[plugin.plugin_key] = _format_entry(plugin, latest)

    if client:
        await client.set(CACHE_KEY, canonical_registry_json(registry), ex=settings.redis_cache_ttl)

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
        await redis.set(MD5_KEY, md5, ex=settings.redis_cache_ttl)

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
    return {
        "total_plugins": total_plugins or 0,
        "total_active_versions": total_versions or 0,
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


def _format_entry(plugin: Plugin, version: PluginVersion) -> dict[str, Any]:
    scan = version.scan
    if scan:
        sec_scan = {
            "virustotal": {"pass": bool(scan.virustotal_pass), "msg": scan.virustotal_msg or ""},
            "llm_agent": {"pass": bool(scan.llm_agent_pass), "msg": scan.llm_agent_msg or ""},
        }
    else:
        sec_scan = {
            "virustotal": {"pass": False, "msg": "not scanned"},
            "llm_agent": {"pass": False, "msg": "not scanned"},
        }

    return {
        "display_name": plugin.display_name,
        "desc": plugin.description,
        "author": plugin.author,
        "repo": plugin.repo_url,
        "tags": [t.name for t in plugin.tags],
        "social_link": plugin.social_link,
        "stars": plugin.stars,
        "version": version.version,
        "updated_at": version.created_at.isoformat() if version.created_at else "",
        "logo": _logo_url(plugin.logo_s3_key),
        "commit_sha": version.commit_sha,
        "download_url": version.download_url or "",
        "sec_scan": sec_scan,
        "i18n": {i.locale: i.data for i in plugin.i18n_entries},
        "astrbot_version": plugin.astrbot_version,
        "support_platforms": plugin.support_platforms or [],
        "category": plugin.category,
    }


def _logo_url(logo_s3_key: str | None) -> str:
    if not logo_s3_key:
        return ""
    return f"{settings.s3_public_url.rstrip('/')}/{logo_s3_key.lstrip('/')}"


async def _fetch_active_plugins(db: AsyncSession) -> list[Plugin]:
    result = await db.execute(
        select(Plugin)
        .where(Plugin.status == "active")
        .options(
            selectinload(Plugin.tags),
            selectinload(Plugin.i18n_entries),
            selectinload(Plugin.versions).selectinload(PluginVersion.scan),
        )
    )
    return list(result.scalars().unique().all())
