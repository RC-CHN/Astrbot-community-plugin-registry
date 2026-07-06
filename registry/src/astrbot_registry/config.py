from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode


# Project root, so .env is always loaded from the repo root regardless of CWD.
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    deployment_mode: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_reload: bool = True
    log_level: str = "info"
    docs_enabled: bool = True
    trusted_hosts: Annotated[list[str], NoDecode] = ["*"]
    cors_allow_origins: Annotated[list[str], NoDecode] = []
    security_headers_enabled: bool = True
    hsts_enabled: bool = False
    hsts_max_age_seconds: int = 31536000
    bootstrap_api_enabled: bool = False
    public_cache_max_age: int = 60
    bootstrap_admin_username: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_role: str = "admin"

    # Database
    database_url: str = (
        "postgresql+asyncpg://astrbot:astrbot_secret@localhost:5432/astrbot_registry"
    )
    database_auto_migrate: bool = True

    # S3 (SeaweedFS)
    s3_endpoint: str = "http://localhost:8333"
    s3_access_key: str = "admin"
    s3_secret_key: str = "adminadmin"
    s3_bucket: str = "astrbot-plugins"
    s3_public_url: str = "http://localhost:8333/astrbot-plugins"
    s3_region: str = "us-east-1"
    s3_auto_create_bucket: bool = True
    s3_connect_timeout: int = 3
    s3_read_timeout: int = 10
    s3_max_attempts: int = 2

    # Redis
    redis_url: str | None = "redis://localhost:6379"
    redis_cache_ttl: int = 3600
    redis_task_queue_key: str = "registry_tasks"
    redis_task_dead_letter_queue_key: str = "registry_tasks_dead"
    task_max_attempts: int = 3
    task_retry_delay_seconds: int = 5

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 1 day
    jwt_refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    login_rate_limit_enabled: bool = True
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 300
    login_rate_limit_block_seconds: int = 900

    # Security scans
    virustotal_api_key: str = ""
    virustotal_timeout_seconds: int = 120
    virustotal_poll_interval_seconds: int = 5
    virustotal_max_poll_attempts: int = 24
    virustotal_max_direct_upload_bytes: int = 32 * 1024 * 1024
    llm_agent_enabled: bool = False
    llm_agent_base_url: str = ""
    llm_agent_model: str = ""
    llm_agent_api_key: str = ""
    llm_agent_max_context_chars: int = 200000
    scan_pass_when_unconfigured: bool = True
    scan_unconfigured_message: str = "Scan not configured"

    # Upload/build limits
    max_upload_bytes: int = 50 * 1024 * 1024
    max_unzip_bytes: int = 200 * 1024 * 1024
    max_zip_entries: int = 2000
    max_single_file_bytes: int = 50 * 1024 * 1024
    max_release_zip_bytes: int = 50 * 1024 * 1024
    git_clone_timeout: int = 120
    build_network_disabled: bool = True
    git_allowed_hosts: Annotated[list[str], NoDecode] = ["github.com"]
    git_temp_prefix: str = "astrbot-repo-"
    webhook_auto_version: str = "auto"

    # Webhooks
    github_webhook_secret: str = ""
    github_webhook_require_secret: bool = True

    # S3 object layout
    s3_plugins_prefix: str = "plugins"
    s3_unknown_author: str = "unknown"

    model_config = {
        "env_file": ROOT_DIR / ".env",
        "env_file_encoding": "utf-8",
    }

    @field_validator("git_allowed_hosts", "trusted_hosts", "cors_allow_origins", mode="before")
    @classmethod
    def parse_csv_list(cls, value):
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
