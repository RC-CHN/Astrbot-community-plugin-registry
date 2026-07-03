"""Worker entrypoint for queued build and scan tasks."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

from redis.exceptions import TimeoutError as RedisTimeoutError

from .cache import get_redis
from .database import async_session
from .services.build_service import build_from_repo
from .services.plugin_service import get_plugin
from .services.scan_service import scan_version
from .services.task_queue import QUEUE_KEY, requeue_task

logger = logging.getLogger(__name__)


async def pop_task(redis_client) -> dict | None:
    try:
        item = await redis_client.blpop(QUEUE_KEY, timeout=5)
    except RedisTimeoutError:
        return None
    if item is None:
        return None
    _, raw = item
    task = json.loads(raw)
    if "payload" not in task:
        task = {"type": task.get("type"), "payload": task.get("payload") or {}}
    task.setdefault("attempts", 0)
    return task


async def handle_task(task: dict) -> None:
    task_type = task.get("type")
    payload = task.get("payload") or {}
    async with async_session() as db:
        if task_type == "build":
            plugin = await get_plugin(db, uuid.UUID(payload["plugin_id"]))
            if plugin is None:
                logger.warning("Skipping build task for missing plugin %s", payload["plugin_id"])
                return
            await build_from_repo(
                db,
                plugin,
                payload["version"],
                ref=payload.get("ref"),
                created_by=payload.get("user_id"),
            )
        elif task_type == "scan":
            await scan_version(db, uuid.UUID(payload["version_id"]), providers=payload.get("providers"))
        else:
            logger.warning("Unknown task type: %s", task_type)


async def run_worker() -> None:
    redis = await get_redis()
    if redis is None:
        raise RuntimeError("Redis is required to run the worker")

    logger.info("Registry worker started")
    while True:
        task = None
        try:
            task = await pop_task(redis)
            if task is None:
                continue
            await handle_task(task)
        except Exception as exc:
            logger.exception("Background task failed")
            if task is not None:
                async with async_session() as db:
                    requeued = await requeue_task(task, exc, db=db)
                if not requeued:
                    logger.error("Task moved to dead-letter queue: %s", task.get("id"))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Registry worker stopped")


if __name__ == "__main__":
    main()
