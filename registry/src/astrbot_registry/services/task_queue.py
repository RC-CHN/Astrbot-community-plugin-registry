"""Lightweight Redis-backed task queue for build and scan jobs."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import get_redis
from ..config import settings
from .runtime_config import runtime_task_max_attempts, runtime_task_retry_delay_seconds
from .task_observability import create_worker_task, mark_task_dead, mark_task_retrying

QUEUE_KEY = settings.redis_task_queue_key
DELAYED_QUEUE_KEY = settings.redis_task_delayed_queue_key
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


async def enqueue_task(
    task_type: str,
    payload: dict[str, Any],
    db: AsyncSession | None = None,
    *,
    delay_seconds: float = 0,
) -> str | None:
    """Queue a background task.

    Returns None when Redis is unavailable so API handlers can use a local
    development fallback.
    """
    redis = await get_redis()
    if redis is None:
        return None
    max_attempts = await runtime_task_max_attempts(db)
    task_id = str(uuid.uuid4())
    if db is not None:
        record = await create_worker_task(
            db,
            task_type,
            payload,
            task_id=task_id,
            max_attempts=max_attempts,
            delay_seconds=delay_seconds,
        )
        task_id = str(record.id)
    await push_task(
        redis,
        create_task_envelope(
            task_type,
            payload,
            task_id=task_id,
            max_attempts=max_attempts,
        ),
        delay_seconds=delay_seconds,
    )
    return task_id


def encode_task(task: dict[str, Any]) -> str:
    return json.dumps(task, separators=(",", ":"))


async def push_task(redis, task: dict[str, Any], *, delay_seconds: float = 0) -> None:
    encoded = encode_task(task)
    if delay_seconds > 0:
        await redis.zadd(DELAYED_QUEUE_KEY, {encoded: time.time() + delay_seconds})
        return
    await redis.rpush(QUEUE_KEY, encoded)


async def promote_due_tasks(redis, *, limit: int = 100) -> int:
    raw_tasks = await redis.zrangebyscore(DELAYED_QUEUE_KEY, 0, time.time(), start=0, num=limit)
    promoted = 0
    for raw in raw_tasks:
        removed = await redis.zrem(DELAYED_QUEUE_KEY, raw)
        if removed:
            await redis.rpush(QUEUE_KEY, raw)
            promoted += 1
    return promoted


async def requeue_task(task: dict[str, Any], error: Exception, db: AsyncSession | None = None) -> bool:
    redis = await get_redis()
    if redis is None:
        return False

    task["attempts"] = int(task.get("attempts") or 0) + 1
    task["last_error"] = str(error)
    max_attempts = int(task.get("max_attempts") or await runtime_task_max_attempts(db))
    if task["attempts"] >= max_attempts:
        if db is not None:
            await mark_task_dead(db, task.get("id"), attempts=task["attempts"], error=str(error))
        await redis.rpush(DEAD_LETTER_QUEUE_KEY, encode_task(task))
        return False

    retry_delay = await runtime_task_retry_delay_seconds(db)
    if db is not None:
        await mark_task_retrying(
            db,
            task.get("id"),
            attempts=task["attempts"],
            error=str(error),
            delay_seconds=retry_delay,
        )
    await push_task(redis, task, delay_seconds=retry_delay)
    return True
