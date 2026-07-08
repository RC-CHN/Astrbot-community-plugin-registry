"""Persistent task state and worker heartbeat helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import os
import socket
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import get_redis
from ..config import settings
from ..models import PluginVersion, WorkerTask

WORKER_HEARTBEAT_PREFIX = "registry_worker:"
WORKER_HEARTBEAT_TTL_SECONDS = 90


def now_utc() -> datetime:
    return datetime.now(UTC)


def payload_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    allowed = {
        "plugin_id",
        "version_id",
        "version",
        "ref",
        "repo_url",
        "providers",
    }
    return {key: value for key, value in payload.items() if key in allowed and value not in (None, "")}


def stored_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return the task payload safe to persist for operator visibility."""
    if not payload:
        return {}
    redacted = {key: value for key, value in payload.items() if key != "temporary_token"}
    if payload.get("temporary_token"):
        redacted["temporary_token_present"] = True
    return redacted


async def create_worker_task(
    db: AsyncSession,
    task_type: str,
    payload: dict[str, Any],
    *,
    task_id: str | None = None,
    max_attempts: int | None = None,
    delay_seconds: float = 0,
) -> WorkerTask:
    plugin_id, version_id = await _task_refs(db, payload)
    task = WorkerTask(
        id=uuid.UUID(task_id) if task_id else uuid.uuid4(),
        task_type=task_type,
        status="delayed" if delay_seconds > 0 else "queued",
        plugin_id=plugin_id,
        version_id=version_id,
        provider=_task_provider(payload),
        payload=stored_payload(payload),
        max_attempts=max_attempts or settings.task_max_attempts,
        next_run_at=now_utc() + timedelta(seconds=delay_seconds) if delay_seconds > 0 else None,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def mark_task_running(db: AsyncSession, task_id: str | None, *, worker_id: str, attempts: int) -> None:
    task = await _get_task(db, task_id)
    if task is None:
        return
    task.status = "running"
    task.started_at = now_utc()
    task.finished_at = None
    task.next_run_at = None
    task.worker_id = worker_id
    task.attempts = attempts
    task.last_error = None
    await db.commit()


async def mark_task_succeeded(db: AsyncSession, task_id: str | None) -> None:
    task = await _get_task(db, task_id)
    if task is None:
        return
    task.status = "succeeded"
    finished_at = now_utc()
    task.finished_at = finished_at
    task.next_run_at = None
    task.duration_ms = _duration_ms(task.started_at, finished_at)
    await db.commit()


async def mark_task_retrying(
    db: AsyncSession,
    task_id: str | None,
    *,
    attempts: int,
    error: str,
    delay_seconds: int,
) -> None:
    task = await _get_task(db, task_id)
    if task is None:
        return
    task.status = "retrying"
    finished_at = now_utc()
    task.finished_at = finished_at
    task.duration_ms = _duration_ms(task.started_at, finished_at)
    task.attempts = attempts
    task.last_error = error
    task.next_run_at = finished_at + timedelta(seconds=delay_seconds)
    await db.commit()


async def mark_task_dead(db: AsyncSession, task_id: str | None, *, attempts: int, error: str) -> None:
    task = await _get_task(db, task_id)
    if task is None:
        return
    task.status = "dead"
    finished_at = now_utc()
    task.finished_at = finished_at
    task.duration_ms = _duration_ms(task.started_at, finished_at)
    task.attempts = attempts
    task.last_error = error
    task.next_run_at = None
    await db.commit()


async def list_worker_tasks(
    db: AsyncSession,
    *,
    status: str | None = None,
    task_type: str | None = None,
    plugin_id: str | None = None,
    version_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[WorkerTask], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = select(WorkerTask)
    count_query = select(func.count(WorkerTask.id))
    filters = []
    if status:
        filters.append(WorkerTask.status == status)
    if task_type:
        filters.append(WorkerTask.task_type == task_type)
    if plugin_id:
        filters.append(WorkerTask.plugin_id == uuid.UUID(plugin_id))
    if version_id:
        filters.append(WorkerTask.version_id == uuid.UUID(version_id))
    for condition in filters:
        query = query.where(condition)
        count_query = count_query.where(condition)
    query = query.order_by(WorkerTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    total = await db.scalar(count_query)
    return list(result.scalars()), int(total or 0)


async def get_worker_task(db: AsyncSession, task_id: uuid.UUID) -> WorkerTask | None:
    return await db.get(WorkerTask, task_id)


async def task_status_counts(db: AsyncSession) -> dict[str, int]:
    result = await db.execute(select(WorkerTask.status, func.count(WorkerTask.id)).group_by(WorkerTask.status))
    counts = {status: int(count) for status, count in result.all()}
    for status in ("queued", "delayed", "running", "retrying", "succeeded", "failed", "dead", "cancelled"):
        counts.setdefault(status, 0)
    return counts


def task_to_dict(task: WorkerTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "task_type": task.task_type,
        "status": task.status,
        "plugin_id": str(task.plugin_id) if task.plugin_id else None,
        "version_id": str(task.version_id) if task.version_id else None,
        "provider": task.provider,
        "payload_summary": payload_summary(task.payload),
        "attempts": task.attempts,
        "max_attempts": task.max_attempts,
        "queued_at": task.queued_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "next_run_at": task.next_run_at,
        "worker_id": task.worker_id,
        "duration_ms": task.duration_ms,
        "last_error": task.last_error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def make_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


async def write_worker_heartbeat(redis, worker_id: str, *, current_task_id: str | None = None) -> None:
    payload = {
        "worker_id": worker_id,
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "heartbeat_at": now_utc().isoformat(),
        "current_task_id": current_task_id,
    }
    key = WORKER_HEARTBEAT_PREFIX + worker_id
    await redis.set(key, json.dumps(payload, separators=(",", ":")), ex=WORKER_HEARTBEAT_TTL_SECONDS)


async def worker_runtime_status(db: AsyncSession) -> dict[str, Any]:
    redis = await get_redis()
    status = {
        "redis_connected": redis is not None,
        "queue_length": 0,
        "delayed_length": 0,
        "dead_letter_length": 0,
        "active_workers": [],
        "tasks_by_status": await task_status_counts(db),
    }
    if redis is None:
        return status

    from .task_queue import DEAD_LETTER_QUEUE_KEY, DELAYED_QUEUE_KEY, QUEUE_KEY

    status["queue_length"] = int(await redis.llen(QUEUE_KEY))
    status["delayed_length"] = int(await redis.zcard(DELAYED_QUEUE_KEY))
    status["dead_letter_length"] = int(await redis.llen(DEAD_LETTER_QUEUE_KEY))
    workers = []
    for key in await redis.keys(WORKER_HEARTBEAT_PREFIX + "*"):
        raw = await redis.get(key)
        if raw is None:
            continue
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            workers.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    workers.sort(key=lambda item: item.get("worker_id") or "")
    status["active_workers"] = workers
    return status


async def _task_refs(db: AsyncSession, payload: dict[str, Any]) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    plugin_id = _uuid_or_none(payload.get("plugin_id"))
    version_id = _uuid_or_none(payload.get("version_id"))
    if version_id and plugin_id is None:
        version_plugin_id = await db.scalar(select(PluginVersion.plugin_id).where(PluginVersion.id == version_id))
        if version_plugin_id:
            plugin_id = version_plugin_id
    return plugin_id, version_id


def _task_provider(payload: dict[str, Any]) -> str | None:
    provider = payload.get("provider")
    if isinstance(provider, str) and provider:
        return provider
    providers = payload.get("providers")
    if isinstance(providers, list) and providers:
        return ",".join(str(item) for item in providers)
    return None


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


async def _get_task(db: AsyncSession, task_id: str | None) -> WorkerTask | None:
    if not task_id:
        return None
    try:
        parsed = uuid.UUID(str(task_id))
    except ValueError:
        return None
    return await db.get(WorkerTask, parsed)


def _duration_ms(started_at: datetime | None, finished_at: datetime) -> int | None:
    if started_at is None:
        return None
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    return max(0, int((finished_at - started_at).total_seconds() * 1000))
