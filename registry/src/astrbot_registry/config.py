from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


# Project root, so .env is always loaded from the repo root regardless of CWD.
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_reload: bool = True
    log_level: str = "info"
    public_cache_max_age: int = 60

    # Database
    database_url: str = (
        "postgresql+asyncpg://astrbot:astrbot_secret@localhost:5432/astrbot_registry"
    )

    # S3 (SeaweedFS)
    s3_endpoint: str = "http://localhost:8333"
    s3_access_key: str = "admin"
    s3_secret_key: str = "adminadmin"
    s3_bucket: str = "astrbot-plugins"
    s3_public_url: str = "http://localhost:8333/astrbot-plugins"
    s3_region: str = "us-east-1"
    s3_auto_create_bucket: bool = True

    # Redis
    redis_url: str | None = "redis://localhost:6379"
    redis_cache_ttl: int = 3600
    redis_task_queue_key: str = "registry_tasks"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 1 day
    jwt_refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Security scans
    virustotal_api_key: str = ""
    llm_agent_enabled: bool = False
    llm_agent_base_url: str = ""
    llm_agent_api_key: str = ""
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
    git_allowed_hosts: list[str] = ["github.com"]
    git_temp_prefix: str = "astrbot-repo-"
    webhook_auto_version: str = "auto"

    # Webhooks
    github_webhook_secret: str = ""

    # S3 object layout
    s3_plugins_prefix: str = "plugins"
    s3_unknown_author: str = "unknown"

    model_config = {
        "env_file": ROOT_DIR / ".env",
        "env_file_encoding": "utf-8",
    }

    @field_validator("git_allowed_hosts", mode="before")
    @classmethod
    def parse_csv_list(cls, value):
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
