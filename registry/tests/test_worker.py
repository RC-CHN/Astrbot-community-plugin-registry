import pytest
from redis.exceptions import TimeoutError as RedisTimeoutError

from astrbot_registry.services import task_queue
from astrbot_registry.services.task_queue import create_task_envelope, requeue_task
from astrbot_registry.worker import pop_task


class FakeRedis:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.items = []

    async def blpop(self, key: str, timeout: int):
        if self.error is not None:
            raise self.error
        return self.result

    async def rpush(self, key: str, value: str):
        self.items.append((key, value))


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
