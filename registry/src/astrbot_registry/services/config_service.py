"""System configuration key-value service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import SystemConfig
from .runtime_config import clear_runtime_config_cache

SENSITIVE_CONFIG_KEYS = {
    "GITHUB_WEBHOOK_SECRET",
    "GIT_HTTP_PROXY",
    "VIRUSTOTAL_API_KEY",
    "LLM_AGENT_API_KEY",
}

EFFECTIVE_CONFIG_DEFAULTS = {
    "PUBLIC_CACHE_MAX_AGE": settings.public_cache_max_age,
    "REDIS_CACHE_TTL": settings.redis_cache_ttl,
    "S3_PUBLIC_URL": settings.s3_public_url,
    "S3_PLUGINS_PREFIX": settings.s3_plugins_prefix,
    "S3_UNKNOWN_AUTHOR": settings.s3_unknown_author,
    "MAX_UPLOAD_BYTES": settings.max_upload_bytes,
    "MAX_UNZIP_BYTES": settings.max_unzip_bytes,
    "MAX_ZIP_ENTRIES": settings.max_zip_entries,
    "MAX_SINGLE_FILE_BYTES": settings.max_single_file_bytes,
    "MAX_RELEASE_ZIP_BYTES": settings.max_release_zip_bytes,
    "GIT_ALLOWED_HOSTS": ",".join(settings.git_allowed_hosts),
    "GIT_CLONE_TIMEOUT": settings.git_clone_timeout,
    "GIT_PREFLIGHT_TIMEOUT": settings.git_preflight_timeout,
    "GIT_MAX_REPO_SIZE_KB": settings.git_max_repo_size_kb,
    "GIT_HTTP_PROXY": settings.git_http_proxy,
    "SCAN_ENABLED_PROVIDERS": ",".join(settings.scan_enabled_providers),
    "SCAN_PASS_WHEN_UNCONFIGURED": settings.scan_pass_when_unconfigured,
    "SCAN_UNCONFIGURED_MESSAGE": settings.scan_unconfigured_message,
    "SCAN_REQUIRE_HUMAN_REVIEW": settings.scan_require_human_review,
    "SCAN_AUTO_PUBLISH_ENABLED": settings.scan_auto_publish_enabled,
    "VIRUSTOTAL_TIMEOUT_SECONDS": settings.virustotal_timeout_seconds,
    "VIRUSTOTAL_POLL_INTERVAL_SECONDS": settings.virustotal_poll_interval_seconds,
    "VIRUSTOTAL_MAX_POLL_INTERVAL_SECONDS": settings.virustotal_max_poll_interval_seconds,
    "VIRUSTOTAL_MAX_POLL_ATTEMPTS": settings.virustotal_max_poll_attempts,
    "VIRUSTOTAL_MAX_WAIT_SECONDS": settings.virustotal_max_wait_seconds,
    "VIRUSTOTAL_MAX_DIRECT_UPLOAD_BYTES": settings.virustotal_max_direct_upload_bytes,
    "CLAMAV_HOST": settings.clamav_host,
    "CLAMAV_PORT": settings.clamav_port,
    "CLAMAV_TIMEOUT_SECONDS": settings.clamav_timeout_seconds,
    "CLAMAV_STREAM_CHUNK_BYTES": settings.clamav_stream_chunk_bytes,
    "CLAMAV_MAX_STREAM_BYTES": settings.clamav_max_stream_bytes,
    "LLM_AGENT_BASE_URL": settings.llm_agent_base_url,
    "LLM_AGENT_MODEL": settings.llm_agent_model,
    "LLM_AGENT_MAX_CONTEXT_CHARS": settings.llm_agent_max_context_chars,
    "TASK_MAX_ATTEMPTS": settings.task_max_attempts,
    "TASK_RETRY_DELAY_SECONDS": settings.task_retry_delay_seconds,
    "WEBHOOK_AUTO_VERSION": settings.webhook_auto_version,
    "GITHUB_WEBHOOK_SECRET": settings.github_webhook_secret,
    "VIRUSTOTAL_API_KEY": settings.virustotal_api_key,
    "LLM_AGENT_API_KEY": settings.llm_agent_api_key,
}


async def list_config(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(SystemConfig))
    return {item.key: item.value for item in result.scalars().all()}


async def list_config_response(db: AsyncSession) -> dict:
    values = await list_config(db)
    return build_config_response(values)


def build_config_response(values: dict[str, str]) -> dict:
    safe_values = {
        key: value
        for key, value in values.items()
        if key not in SENSITIVE_CONFIG_KEYS
    }
    sensitive_status = {
        key: bool(values.get(key) or EFFECTIVE_CONFIG_DEFAULTS.get(key))
        for key in SENSITIVE_CONFIG_KEYS
    }
    effective_values = {}
    for key, default in EFFECTIVE_CONFIG_DEFAULTS.items():
        if key in SENSITIVE_CONFIG_KEYS:
            continue
        effective_values[key] = str(values.get(key, default))
    return {
        "values": safe_values,
        "effective_values": effective_values,
        "sensitive_status": sensitive_status,
        "sensitive_keys": sorted(SENSITIVE_CONFIG_KEYS),
        "deployment_values": deployment_values(),
    }


def deployment_values() -> dict[str, str]:
    return {
        "DEPLOYMENT_MODE": settings.deployment_mode,
        "DATABASE_URL": _mask_url_secret(settings.database_url),
        "REDIS_URL": _mask_url_secret(settings.redis_url or ""),
        "S3_ENDPOINT": settings.s3_endpoint,
        "S3_ACCESS_KEY": _mask_secret(settings.s3_access_key),
        "S3_SECRET_KEY": _mask_secret(settings.s3_secret_key),
        "S3_BUCKET": settings.s3_bucket,
        "S3_REGION": settings.s3_region,
        "JWT_SECRET": _mask_secret(settings.jwt_secret),
        "JWT_ALGORITHM": settings.jwt_algorithm,
        "APP_HOST": settings.app_host,
        "APP_PORT": str(settings.app_port),
        "APP_RELOAD": str(settings.app_reload),
        "DOCS_ENABLED": str(settings.docs_enabled),
        "TRUSTED_HOSTS": ",".join(settings.trusted_hosts),
        "CORS_ALLOW_ORIGINS": ",".join(settings.cors_allow_origins),
        "SECURITY_HEADERS_ENABLED": str(settings.security_headers_enabled),
        "HSTS_ENABLED": str(settings.hsts_enabled),
        "TRUST_PROXY_HEADERS": str(settings.trust_proxy_headers),
        "TRUSTED_PROXY_CIDRS": ",".join(settings.trusted_proxy_cidrs),
        "BOOTSTRAP_API_ENABLED": str(settings.bootstrap_api_enabled),
        "GITHUB_WEBHOOK_REQUIRE_SECRET": str(settings.github_webhook_require_secret),
        "LOGIN_RATE_LIMIT_ENABLED": str(settings.login_rate_limit_enabled),
        "LOG_LEVEL": settings.log_level,
    }


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 2:
        return "••••"
    if len(value) <= 6:
        return f"{value[0]}••{value[-1]}"
    return f"{value[:3]}••••{value[-2:]}"


def _mask_url_secret(value: str) -> str:
    if "@" not in value or "://" not in value:
        return value
    scheme, rest = value.split("://", 1)
    credentials, host = rest.split("@", 1)
    if ":" not in credentials:
        return value
    username, _ = credentials.split(":", 1)
    return f"{scheme}://{username}:••••@{host}"


async def update_config(db: AsyncSession, values: dict[str, str]) -> dict:
    for key, value in values.items():
        item = await db.get(SystemConfig, key)
        if value == "":
            if item is not None:
                await db.delete(item)
            continue
        if item is None:
            db.add(SystemConfig(key=key, value=value))
        else:
            item.value = value
    await db.commit()
    await clear_runtime_config_cache()
    return await list_config_response(db)
