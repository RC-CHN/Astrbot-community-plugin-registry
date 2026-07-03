"""Lightweight Redis-backed task queue for build and scan jobs."""

from __future__ import annotations

import json
from typing import Any

from ..cache import get_redis
from ..config import settings

QUEUE_KEY = settings.redis_task_queue_key


async def enqueue_task(task_type: str, payload: dict[str, Any]) -> bool:
    """Queue a background task.

    Returns False when Redis is unavailable so API handlers can use a local
    development fallback.
    """
    redis = await get_redis()
    if redis is None:
        return False
    await redis.rpush(
        QUEUE_KEY,
        json.dumps({"type": task_type, "payload": payload}, separators=(",", ":")),
    )
    return True
