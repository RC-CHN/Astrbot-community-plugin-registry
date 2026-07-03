"""Async Redis cache client."""

import redis.asyncio as redis

from .config import settings

_redis: redis.Redis | None = None


async def get_redis() -> redis.Redis | None:
    """Return a connected Redis client, or None if Redis is not configured/available."""
    global _redis
    if _redis is not None:
        return _redis
    if not settings.redis_url:
        return None
    try:
        client = redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis = client
    except Exception:
        return None
    return _redis


async def close_redis() -> None:
    """Close the global Redis connection."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
