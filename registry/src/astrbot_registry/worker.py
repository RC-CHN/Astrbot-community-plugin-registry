"""Worker entrypoint for queued build and scan tasks."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import uuid

from redis.exceptions import TimeoutError as RedisTimeoutError

from .cache import get_redis
from .database import async_session
from .services.build_service import build_from_repo
from .services.plugin_service import get_plugin
from .services.scan_service import poll_virustotal_analysis, scan_version
from .services.submit_service import submit_repo
from .services.task_observability import (
    make_worker_id,
    mark_task_running,
    mark_task_succeeded,
    write_worker_heartbeat,
)
from .services.task_queue import QUEUE_KEY, promote_due_tasks, requeue_task

logger = logging.getLogger(__name__)


def _install_shutdown_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        logger.info("Worker shutdown requested; finishing current task before exit")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            signal.signal(sig, lambda _signum, _frame: loop.call_soon_threadsafe(request_stop))


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
                credential_id=payload.get("credential_id"),
                temporary_token=payload.get("temporary_token"),
                changelog=payload.get("changelog", ""),
                created_by=payload.get("user_id"),
            )
        elif task_type == "scan":
            await scan_version(db, uuid.UUID(payload["version_id"]), providers=payload.get("providers"))
        elif task_type == "virustotal_poll":
            await poll_virustotal_analysis(db, uuid.UUID(payload["version_id"]))
        elif task_type == "submit":
            await submit_repo(
                db,
                repo_url=payload["repo_url"],
                version=payload.get("version"),
                ref=payload.get("ref"),
                credential_id=payload.get("credential_id"),
                temporary_token=payload.get("temporary_token"),
                changelog=payload.get("changelog", ""),
                user_id=payload.get("user_id"),
            )
        else:
            logger.warning("Unknown task type: %s", task_type)


async def run_worker() -> None:
    redis = await get_redis()
    if redis is None:
        raise RuntimeError("Redis is required to run the worker")

    worker_id = make_worker_id()
    stop_event = asyncio.Event()
    _install_shutdown_handlers(stop_event)
    logger.info("Registry worker started: %s", worker_id)
    while not stop_event.is_set():
        task = None
        try:
            await write_worker_heartbeat(redis, worker_id)
            await promote_due_tasks(redis)
            task = await pop_task(redis)
            if task is None:
                continue
            async with async_session() as db:
                await mark_task_running(
                    db,
                    task.get("id"),
                    worker_id=worker_id,
                    attempts=int(task.get("attempts") or 0),
                )
            await write_worker_heartbeat(redis, worker_id, current_task_id=task.get("id"))
            await handle_task(task)
            async with async_session() as db:
                await mark_task_succeeded(db, task.get("id"))
            await write_worker_heartbeat(redis, worker_id)
        except Exception as exc:
            logger.exception("Background task failed")
            if task is not None:
                async with async_session() as db:
                    requeued = await requeue_task(task, exc, db=db)
                if not requeued:
                    logger.error("Task moved to dead-letter queue: %s", task.get("id"))
            await write_worker_heartbeat(redis, worker_id)
    logger.info("Registry worker drained and stopped: %s", worker_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Registry worker stopped")


if __name__ == "__main__":
    main()
