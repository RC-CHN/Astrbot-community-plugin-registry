from fastapi import APIRouter, Query

public_router = APIRouter(tags=["public"])


@public_router.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@public_router.get("/plugins")
async def list_plugins() -> dict:
    """Return the full plugin registry in AstrBot-compatible format."""
    # TODO: implement registry service
    return {}


@public_router.get("/plugins-md5")
@public_router.get("/plugins-md5.json")
async def registry_md5() -> dict:
    """Return MD5 of the cached registry JSON.

    AstrBot appends `-md5.json` to custom source URLs, so both endpoints
    must be exposed.
    """
    # TODO: implement md5 caching
    return {"md5": "00000000000000000000000000000000"}


@public_router.get("/plugins/{plugin_key}")
async def get_plugin(plugin_key: str) -> dict:
    # TODO: implement single plugin lookup
    return {"plugin_key": plugin_key}


@public_router.get("/plugin/{plugin_key}/logo")
async def get_plugin_logo(plugin_key: str) -> dict:
    # TODO: proxy logo from S3
    return {"plugin_key": plugin_key}


@public_router.get("/plugin/{plugin_key}/download")
async def download_plugin(plugin_key: str) -> dict:
    # TODO: redirect to S3 and count download
    return {"plugin_key": plugin_key}


@public_router.get("/search")
async def search_plugins(
    q: str | None = Query(None),
    tags: list[str] | None = Query(None),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> dict:
    # TODO: implement search
    return {
        "q": q,
        "tags": tags,
        "category": category,
        "page": page,
        "size": size,
        "items": [],
    }


@public_router.get("/stats")
async def registry_stats() -> dict:
    # TODO: implement statistics
    return {"total_plugins": 0}
