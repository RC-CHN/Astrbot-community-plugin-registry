import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..api.deps import get_db
from ..config import settings
from ..models import Plugin
from ..services.plugin_service import get_latest_version, get_plugin_by_key
from ..services.registry_service import (
    canonical_registry_bytes,
    generate_registry_json,
    get_registry_md5,
    get_stats,
)
from ..services.s3_service import build_public_url
from ..services.stats_service import increment_download_count, increment_install_count

public_router = APIRouter(tags=["public"])


@public_router.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@public_router.get("/plugins")
async def list_plugins(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Return the full plugin registry in AstrBot-compatible format."""
    registry = await generate_registry_json(db)
    md5 = hashlib.md5(canonical_registry_bytes(registry)).hexdigest()
    return JSONResponse(
        content=registry,
        headers={
            "ETag": f'"{md5}"',
            "Cache-Control": f"public, max-age={settings.public_cache_max_age}",
        },
    )


@public_router.get("/plugins-md5")
@public_router.get("/plugins-md5.json")
async def registry_md5(db: AsyncSession = Depends(get_db)) -> dict:
    """Return MD5 of the cached registry JSON.

    AstrBot appends `-md5.json` to custom source URLs, so both endpoints
    must be exposed.
    """
    return {"md5": await get_registry_md5(db)}


@public_router.get("/plugin/{plugin_key}/logo")
async def get_plugin_logo(plugin_key: str, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    plugin = await get_plugin_by_key(db, plugin_key)
    if plugin is None or not plugin.logo_s3_key:
        raise HTTPException(status_code=404, detail="Logo not found")
    return RedirectResponse(url=build_public_url(plugin.logo_s3_key))


@public_router.get("/plugin/{plugin_key}/download")
async def download_plugin(plugin_key: str, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    plugin = await get_plugin_by_key(db, plugin_key)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    latest = await get_latest_version(db, plugin.id)
    if latest is None or not latest.download_url:
        raise HTTPException(status_code=404, detail="No active version available")
    await increment_download_count(db, latest.id)
    return RedirectResponse(url=latest.download_url)


@public_router.post("/plugin/{plugin_key}/install")
async def record_install(plugin_key: str, db: AsyncSession = Depends(get_db)) -> dict:
    plugin = await get_plugin_by_key(db, plugin_key)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    latest = await get_latest_version(db, plugin.id)
    if latest is None:
        raise HTTPException(status_code=404, detail="No active version available")
    await increment_install_count(db, latest.id)
    return {"status": "recorded"}


@public_router.get("/plugins/search")
@public_router.get("/search")
async def search_plugins(
    q: str | None = Query(None),
    tags: list[str] | None = Query(None),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    stmt = select(Plugin).where(Plugin.status == "active")
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            (Plugin.plugin_key.ilike(pattern))
            | (Plugin.display_name.ilike(pattern))
            | (Plugin.description.ilike(pattern))
        )
    if category:
        stmt = stmt.where(Plugin.category == category)

    result = await db.execute(stmt.options(selectinload(Plugin.tags)))
    plugins = result.scalars().unique().all()

    if tags:
        tags_lower = {t.lower() for t in tags}
        plugins = [
            p for p in plugins if any(t.name.lower() in tags_lower for t in p.tags)
        ]

    total = len(plugins)
    start = (page - 1) * size
    end = start + size
    return {
        "q": q,
        "tags": tags,
        "category": category,
        "page": page,
        "size": size,
        "total": total,
        "items": [
            {
                "plugin_key": p.plugin_key,
                "display_name": p.display_name,
                "desc": p.description,
                "author": p.author,
                "category": p.category,
                "tags": [t.name for t in p.tags],
            }
            for p in plugins[start:end]
        ],
    }


@public_router.get("/plugins/stats")
@public_router.get("/stats")
async def registry_stats(db: AsyncSession = Depends(get_db)) -> dict:
    return await get_stats(db)


@public_router.get("/plugins/{plugin_key}")
async def get_plugin(plugin_key: str, db: AsyncSession = Depends(get_db)) -> dict:
    registry = await generate_registry_json(db)
    if plugin_key not in registry:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return registry[plugin_key]
