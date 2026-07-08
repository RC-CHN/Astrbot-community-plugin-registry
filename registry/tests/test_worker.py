import pytest
import uuid
from redis.exceptions import TimeoutError as RedisTimeoutError

from astrbot_registry.services.errors import ConflictError
from astrbot_registry.services import task_queue
from astrbot_registry.services.task_queue import create_task_envelope, enqueue_task, promote_due_tasks, requeue_task
from astrbot_registry.worker import pop_task


class FakeRedis:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.items = []
        self.delayed = {}

    async def blpop(self, key: str, timeout: int):
        if self.error is not None:
            raise self.error
        return self.result

    async def rpush(self, key: str, value: str):
        self.items.append((key, value))

    async def zadd(self, key: str, mapping: dict[str, float]):
        self.delayed.setdefault(key, {}).update(mapping)

    async def zrangebyscore(self, key: str, min, max, start: int = 0, num: int | None = None):
        values = [
            value
            for value, score in self.delayed.get(key, {}).items()
            if float(min) <= score <= float(max)
        ]
        values.sort()
        if num is None:
            return values[start:]
        return values[start : start + num]

    async def zrem(self, key: str, value: str):
        values = self.delayed.get(key, {})
        if value not in values:
            return 0
        del values[value]
        return 1


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_pop_task_returns_none_for_empty_queue() -> None:
    assert await pop_task(FakeRedis(result=None)) is None


@pytest.mark.asyncio
async def test_pop_task_treats_redis_timeout_as_empty_queue() -> None:
    assert await pop_task(FakeRedis(error=RedisTimeoutError("timeout"))) is None


@pytest.mark.asyncio
async def test_pop_task_parses_queue_payload() -> None:
    task = await pop_task(
        FakeRedis(result=("registry_tasks", '{"id":"1","type":"scan","payload":{}}'))
    )

    assert task == {"id": "1", "type": "scan", "payload": {}, "attempts": 0}


def test_create_task_envelope_adds_retry_metadata() -> None:
    task = create_task_envelope("scan", {"version_id": "v1"}, task_id="task-1")

    assert task["id"] == "task-1"
    assert task["attempts"] == 0
    assert task["max_attempts"] == task_queue.settings.task_max_attempts


@pytest.mark.asyncio
async def test_requeue_task_moves_exhausted_task_to_dead_letter(monkeypatch) -> None:
    redis = FakeRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(task_queue, "get_redis", fake_get_redis)
    monkeypatch.setattr(task_queue.settings, "task_retry_delay_seconds", 0)
    task = create_task_envelope("scan", {}, task_id="task-1", attempts=2, max_attempts=3)

    requeued = await requeue_task(task, RuntimeError("boom"))

    assert requeued is False
    assert redis.items[0][0] == task_queue.DEAD_LETTER_QUEUE_KEY
    assert '"last_error":"boom"' in redis.items[0][1]


@pytest.mark.asyncio
async def test_requeue_task_does_not_retry_non_retryable_registry_error(monkeypatch) -> None:
    redis = FakeRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(task_queue, "get_redis", fake_get_redis)
    task = create_task_envelope("build", {"plugin_id": "p1"}, task_id="task-1", attempts=0, max_attempts=3)

    requeued = await requeue_task(task, ConflictError("duplicate commit"))

    assert requeued is False
    assert redis.delayed == {}
    assert redis.items[0][0] == task_queue.DEAD_LETTER_QUEUE_KEY
    assert '"attempts":1' in redis.items[0][1]
    assert '"last_error":"duplicate commit"' in redis.items[0][1]


@pytest.mark.asyncio
async def test_requeue_task_redacts_temporary_token_in_dead_letter(monkeypatch) -> None:
    redis = FakeRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(task_queue, "get_redis", fake_get_redis)
    task = create_task_envelope(
        "submit",
        {"repo_url": "https://github.com/example/repo", "temporary_token": "ghp_secret"},
        task_id="task-1",
        attempts=2,
        max_attempts=3,
    )

    await requeue_task(task, RuntimeError("boom"))

    assert "ghp_secret" not in redis.items[0][1]
    assert '"temporary_token_present":true' in redis.items[0][1]


@pytest.mark.asyncio
async def test_enqueue_task_creates_observable_task_record(monkeypatch) -> None:
    redis = FakeRedis()
    task_id = uuid.UUID("00000000-0000-0000-0000-000000000123")

    async def fake_get_redis():
        return redis

    async def fake_create_worker_task(db, task_type, payload, **kwargs):
        assert db == "db"
        assert task_type == "scan"
        assert payload == {"version_id": "v1"}
        assert kwargs["max_attempts"] == 3

        class Record:
            id = task_id

        return Record()

    monkeypatch.setattr(task_queue, "get_redis", fake_get_redis)
    monkeypatch.setattr(task_queue, "runtime_task_max_attempts", lambda _db=None: _async_value(3))
    monkeypatch.setattr(task_queue, "create_worker_task", fake_create_worker_task)

    result = await enqueue_task("scan", {"version_id": "v1"}, db="db")  # type: ignore[arg-type]

    assert result == str(task_id)
    assert redis.items[0][0] == task_queue.QUEUE_KEY
    assert f'"id":"{task_id}"' in redis.items[0][1]


@pytest.mark.asyncio
async def test_requeue_task_uses_delayed_queue_for_retry_delay(monkeypatch) -> None:
    redis = FakeRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(task_queue, "get_redis", fake_get_redis)
    monkeypatch.setattr(task_queue.settings, "task_retry_delay_seconds", 30)
    task = create_task_envelope("scan", {}, task_id="task-1", attempts=0, max_attempts=3)

    requeued = await requeue_task(task, RuntimeError("boom"))

    assert requeued is True
    assert redis.items == []
    assert len(redis.delayed[task_queue.DELAYED_QUEUE_KEY]) == 1


@pytest.mark.asyncio
async def test_promote_due_tasks_moves_delayed_items(monkeypatch) -> None:
    redis = FakeRedis()
    task = create_task_envelope("virustotal_poll", {"version_id": "v1"}, task_id="task-1")
    await task_queue.push_task(redis, task, delay_seconds=30)
    monkeypatch.setattr(task_queue.time, "time", lambda: 10**12)

    promoted = await promote_due_tasks(redis)

    assert promoted == 1
    assert redis.items[0][0] == task_queue.QUEUE_KEY
    assert '"type":"virustotal_poll"' in redis.items[0][1]
