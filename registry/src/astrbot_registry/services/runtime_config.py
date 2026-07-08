"""Runtime configuration backed by DB with Redis caching."""

from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import get_redis
from ..config import settings
from ..models import SystemConfig

RUNTIME_CONFIG_CACHE_KEY = "runtime_config"
RUNTIME_CONFIG_CACHE_TTL_SECONDS = 30
KNOWN_SCAN_PROVIDER_ORDER = ("clamav", "virustotal", "llm_agent")
REGISTRATION_MODES = {"disabled", "invite", "approval"}

T = TypeVar("T")


async def get_runtime_values(db: AsyncSession) -> dict[str, str]:
    redis = await get_redis()
    if redis is not None:
        cached = await redis.hgetall(RUNTIME_CONFIG_CACHE_KEY)
        if cached:
            return dict(cached)

    result = await db.execute(select(SystemConfig))
    values = {item.key: item.value for item in result.scalars().all()}
    if redis is not None and values:
        await redis.hset(RUNTIME_CONFIG_CACHE_KEY, mapping=values)
        await redis.expire(RUNTIME_CONFIG_CACHE_KEY, RUNTIME_CONFIG_CACHE_TTL_SECONDS)
    return values


async def clear_runtime_config_cache() -> None:
    redis = await get_redis()
    if redis is not None:
        await redis.delete(RUNTIME_CONFIG_CACHE_KEY)


async def get_runtime_value(
    db: AsyncSession,
    key: str,
    default: T,
    cast: type[T] | None = None,
) -> T:
    values = await get_runtime_values(db)
    raw = values.get(key)
    if raw is None or raw == "":
        return default
    return cast_runtime_value(raw, default, cast)


def cast_runtime_value(raw: str, default: T, cast: type[T] | None = None) -> T:
    target = cast or type(default)
    if target is bool:
        return _to_bool(raw)  # type: ignore[return-value]
    if target is int:
        return int(raw)  # type: ignore[return-value]
    if target is list:
        return [item.strip() for item in raw.split(",") if item.strip()]  # type: ignore[return-value]
    return raw  # type: ignore[return-value]


def _to_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on"}


async def runtime_public_cache_max_age(db: AsyncSession) -> int:
    return await get_runtime_value(db, "PUBLIC_CACHE_MAX_AGE", settings.public_cache_max_age, int)


async def runtime_redis_cache_ttl(db: AsyncSession) -> int:
    return await get_runtime_value(db, "REDIS_CACHE_TTL", settings.redis_cache_ttl, int)


async def runtime_upload_limits(db: AsyncSession) -> dict[str, int]:
    return {
        "max_upload_bytes": await get_runtime_value(db, "MAX_UPLOAD_BYTES", settings.max_upload_bytes, int),
        "max_unzip_bytes": await get_runtime_value(db, "MAX_UNZIP_BYTES", settings.max_unzip_bytes, int),
        "max_zip_entries": await get_runtime_value(db, "MAX_ZIP_ENTRIES", settings.max_zip_entries, int),
        "max_single_file_bytes": await get_runtime_value(
            db,
            "MAX_SINGLE_FILE_BYTES",
            settings.max_single_file_bytes,
            int,
        ),
    }


async def runtime_git_clone_timeout(db: AsyncSession) -> int:
    return await get_runtime_value(db, "GIT_CLONE_TIMEOUT", settings.git_clone_timeout, int)


async def runtime_git_preflight_timeout(db: AsyncSession) -> int:
    return await get_runtime_value(db, "GIT_PREFLIGHT_TIMEOUT", settings.git_preflight_timeout, int)


async def runtime_git_max_repo_size_kb(db: AsyncSession) -> int:
    return await get_runtime_value(db, "GIT_MAX_REPO_SIZE_KB", settings.git_max_repo_size_kb, int)


async def runtime_git_http_proxy(db: AsyncSession) -> str:
    return await get_runtime_value(db, "GIT_HTTP_PROXY", settings.git_http_proxy, str)


async def runtime_github_token(db: AsyncSession) -> str:
    return await get_runtime_value(db, "GITHUB_TOKEN", settings.github_token, str)


async def runtime_git_allowed_hosts(db: AsyncSession) -> list[str]:
    return await get_runtime_value(db, "GIT_ALLOWED_HOSTS", settings.git_allowed_hosts, list)


async def runtime_registration_mode(db: AsyncSession) -> str:
    mode = await get_runtime_value(db, "USER_REGISTRATION_MODE", settings.user_registration_mode, str)
    return normalize_registration_mode(mode)


def normalize_registration_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in REGISTRATION_MODES:
        return "disabled"
    return normalized


async def runtime_scan_defaults(db: AsyncSession) -> dict[str, Any]:
    return {
        "pass_when_unconfigured": await get_runtime_value(
            db,
            "SCAN_PASS_WHEN_UNCONFIGURED",
            settings.scan_pass_when_unconfigured,
            bool,
        ),
        "message": await get_runtime_value(
            db,
            "SCAN_UNCONFIGURED_MESSAGE",
            settings.scan_unconfigured_message,
            str,
        ),
    }


async def runtime_scan_enabled_providers(db: AsyncSession) -> list[str]:
    providers = await get_runtime_value(
        db,
        "SCAN_ENABLED_PROVIDERS",
        settings.scan_enabled_providers,
        list,
    )
    return normalize_scan_provider_list(providers)


def normalize_scan_provider_list(providers: list[str]) -> list[str]:
    normalized = [provider.strip().lower() for provider in providers if provider.strip()]
    if any(provider in {"none", "off", "disabled"} for provider in normalized):
        return []
    selected = set(normalized)
    return [provider for provider in KNOWN_SCAN_PROVIDER_ORDER if provider in selected]


async def runtime_review_policy(db: AsyncSession) -> dict[str, bool]:
    return {
        "require_human_review": await get_runtime_value(
            db,
            "SCAN_REQUIRE_HUMAN_REVIEW",
            settings.scan_require_human_review,
            bool,
        ),
        "auto_publish": await get_runtime_value(
            db,
            "SCAN_AUTO_PUBLISH_ENABLED",
            settings.scan_auto_publish_enabled,
            bool,
        ),
    }


async def runtime_virustotal_config(db: AsyncSession) -> dict[str, Any]:
    return {
        "api_key": await get_runtime_value(db, "VIRUSTOTAL_API_KEY", settings.virustotal_api_key, str),
        "timeout_seconds": await get_runtime_value(
            db,
            "VIRUSTOTAL_TIMEOUT_SECONDS",
            settings.virustotal_timeout_seconds,
            int,
        ),
        "poll_interval_seconds": await get_runtime_value(
            db,
            "VIRUSTOTAL_POLL_INTERVAL_SECONDS",
            settings.virustotal_poll_interval_seconds,
            int,
        ),
        "max_poll_interval_seconds": await get_runtime_value(
            db,
            "VIRUSTOTAL_MAX_POLL_INTERVAL_SECONDS",
            settings.virustotal_max_poll_interval_seconds,
            int,
        ),
        "max_poll_attempts": await get_runtime_value(
            db,
            "VIRUSTOTAL_MAX_POLL_ATTEMPTS",
            settings.virustotal_max_poll_attempts,
            int,
        ),
        "max_wait_seconds": await get_runtime_value(
            db,
            "VIRUSTOTAL_MAX_WAIT_SECONDS",
            settings.virustotal_max_wait_seconds,
            int,
        ),
        "max_direct_upload_bytes": await get_runtime_value(
            db,
            "VIRUSTOTAL_MAX_DIRECT_UPLOAD_BYTES",
            settings.virustotal_max_direct_upload_bytes,
            int,
        ),
    }


async def runtime_clamav_config(db: AsyncSession) -> dict[str, Any]:
    return {
        "host": await get_runtime_value(db, "CLAMAV_HOST", settings.clamav_host, str),
        "port": await get_runtime_value(db, "CLAMAV_PORT", settings.clamav_port, int),
        "timeout_seconds": await get_runtime_value(
            db,
            "CLAMAV_TIMEOUT_SECONDS",
            settings.clamav_timeout_seconds,
            int,
        ),
        "stream_chunk_bytes": await get_runtime_value(
            db,
            "CLAMAV_STREAM_CHUNK_BYTES",
            settings.clamav_stream_chunk_bytes,
            int,
        ),
        "max_stream_bytes": await get_runtime_value(
            db,
            "CLAMAV_MAX_STREAM_BYTES",
            settings.clamav_max_stream_bytes,
            int,
        ),
    }


async def runtime_llm_agent_config(db: AsyncSession) -> dict[str, Any]:
    return {
        "base_url": await get_runtime_value(db, "LLM_AGENT_BASE_URL", settings.llm_agent_base_url, str),
        "model": await get_runtime_value(db, "LLM_AGENT_MODEL", settings.llm_agent_model, str),
        "api_key": await get_runtime_value(db, "LLM_AGENT_API_KEY", settings.llm_agent_api_key, str),
        "max_context_chars": await get_runtime_value(
            db,
            "LLM_AGENT_MAX_CONTEXT_CHARS",
            settings.llm_agent_max_context_chars,
            int,
        ),
    }


async def runtime_task_max_attempts(db: AsyncSession | None = None) -> int:
    if db is None:
        return settings.task_max_attempts
    return await get_runtime_value(db, "TASK_MAX_ATTEMPTS", settings.task_max_attempts, int)


async def runtime_task_retry_delay_seconds(db: AsyncSession | None = None) -> int:
    if db is None:
        return settings.task_retry_delay_seconds
    return await get_runtime_value(db, "TASK_RETRY_DELAY_SECONDS", settings.task_retry_delay_seconds, int)


async def runtime_webhook_secret(db: AsyncSession) -> str:
    return await get_runtime_value(db, "GITHUB_WEBHOOK_SECRET", settings.github_webhook_secret, str)


async def runtime_webhook_auto_version(db: AsyncSession) -> str:
    return await get_runtime_value(db, "WEBHOOK_AUTO_VERSION", settings.webhook_auto_version, str)


async def runtime_s3_public_url(db: AsyncSession) -> str:
    return await get_runtime_value(db, "S3_PUBLIC_URL", settings.s3_public_url, str)


async def runtime_s3_layout(db: AsyncSession) -> dict[str, str]:
    return {
        "plugins_prefix": await get_runtime_value(db, "S3_PLUGINS_PREFIX", settings.s3_plugins_prefix, str),
        "unknown_author": await get_runtime_value(db, "S3_UNKNOWN_AUTHOR", settings.s3_unknown_author, str),
    }


async def runtime_max_release_zip_bytes(db: AsyncSession) -> int:
    return await get_runtime_value(db, "MAX_RELEASE_ZIP_BYTES", settings.max_release_zip_bytes, int)
