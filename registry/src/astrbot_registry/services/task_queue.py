"""Lightweight Redis-backed task queue for build and scan jobs."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from ..cache import get_redis
from ..config import settings

QUEUE_KEY = settings.redis_task_queue_key
DEAD_LETTER_QUEUE_KEY = settings.redis_task_dead_letter_queue_key


def create_task_envelope(
    task_type: str,
    payload: dict[str, Any],
    *,
    task_id: str | None = None,
    attempts: int = 0,
    max_attempts: int | None = None,
    last_error: str | None = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "id": task_id or str(uuid.uuid4()),
        "type": task_type,
        "payload": payload,
        "attempts": attempts,
        "max_attempts": max_attempts or settings.task_max_attempts,
    }
    if last_error:
        envelope["last_error"] = last_error
    return envelope


async def enqueue_task(task_type: str, payload: dict[str, Any]) -> bool:
    """Queue a background task.

    Returns False when Redis is unavailable so API handlers can use a local
    development fallback.
    """
    redis = await get_redis()
    if redis is None:
        return False
    await redis.rpush(QUEUE_KEY, encode_task(create_task_envelope(task_type, payload)))
    return True


def encode_task(task: dict[str, Any]) -> str:
    return json.dumps(task, separators=(",", ":"))


async def requeue_task(task: dict[str, Any], error: Exception) -> bool:
    redis = await get_redis()
    if redis is None:
        return False

    task["attempts"] = int(task.get("attempts") or 0) + 1
    task["last_error"] = str(error)
    if task["attempts"] >= int(task.get("max_attempts") or settings.task_max_attempts):
        await redis.rpush(DEAD_LETTER_QUEUE_KEY, encode_task(task))
        return False

    if settings.task_retry_delay_seconds > 0:
        await asyncio.sleep(settings.task_retry_delay_seconds)
    await redis.rpush(QUEUE_KEY, encode_task(task))
    return True
