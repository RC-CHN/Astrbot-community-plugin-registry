from pathlib import Path

from pydantic_settings import BaseSettings


# Project root, so .env is always loaded from the repo root regardless of CWD.
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

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

    # Upload/build limits
    max_upload_bytes: int = 50 * 1024 * 1024
    max_unzip_bytes: int = 200 * 1024 * 1024
    max_zip_entries: int = 2000
    max_single_file_bytes: int = 50 * 1024 * 1024
    max_release_zip_bytes: int = 50 * 1024 * 1024
    git_clone_timeout: int = 120
    build_network_disabled: bool = True

    # Webhooks
    github_webhook_secret: str = ""

    # App
    log_level: str = "info"

    model_config = {
        "env_file": ROOT_DIR / ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
