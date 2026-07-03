import pytest

from astrbot_registry.services import runtime_config
from astrbot_registry.services.runtime_config import cast_runtime_value, get_runtime_values


class FakeRedis:
    def __init__(self):
        self.hashes = {}
        self.deleted = []

    async def hgetall(self, key: str):
        return self.hashes.get(key, {})

    async def hset(self, key: str, mapping: dict[str, str]):
        self.hashes[key] = dict(mapping)

    async def expire(self, key: str, ttl: int):
        return True

    async def delete(self, key: str):
        self.deleted.append(key)


def test_cast_runtime_values() -> None:
    assert cast_runtime_value("true", False, bool) is True
    assert cast_runtime_value("42", 0, int) == 42
    assert cast_runtime_value("github.com, git.example.com", [], list) == [
        "github.com",
        "git.example.com",
    ]
    assert cast_runtime_value("value", "", str) == "value"


@pytest.mark.asyncio
async def test_get_runtime_values_uses_redis_cache(monkeypatch) -> None:
    redis = FakeRedis()
    redis.hashes[runtime_config.RUNTIME_CONFIG_CACHE_KEY] = {"PUBLIC_CACHE_MAX_AGE": "120"}

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(runtime_config, "get_redis", fake_get_redis)

    values = await get_runtime_values(db=None)  # type: ignore[arg-type]

    assert values == {"PUBLIC_CACHE_MAX_AGE": "120"}


@pytest.mark.asyncio
async def test_clear_runtime_config_cache(monkeypatch) -> None:
    redis = FakeRedis()

    async def fake_get_redis():
        return redis

    monkeypatch.setattr(runtime_config, "get_redis", fake_get_redis)

    await runtime_config.clear_runtime_config_cache()

    assert redis.deleted == [runtime_config.RUNTIME_CONFIG_CACHE_KEY]
