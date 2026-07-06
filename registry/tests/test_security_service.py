from types import SimpleNamespace

import pytest

from astrbot_registry.services.security_service import (
    InMemoryRateLimiter,
    SecurityConfigurationError,
    validate_security_settings,
)


def _settings(**overrides):
    values = {
        "deployment_mode": "production",
        "jwt_secret": "x" * 32,
        "trusted_hosts": ["registry.example.com"],
        "cors_allow_origins": [],
        "docs_enabled": False,
        "bootstrap_api_enabled": False,
        "github_webhook_require_secret": True,
        "scan_pass_when_unconfigured": False,
        "s3_access_key": "registry-prod",
        "s3_secret_key": "s" * 16,
        "bootstrap_admin_username": "",
        "bootstrap_admin_password": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_validate_security_settings_rejects_production_defaults() -> None:
    with pytest.raises(SecurityConfigurationError) as exc:
        validate_security_settings(
            _settings(
                jwt_secret="change-me-in-production",
                trusted_hosts=["*"],
                docs_enabled=True,
                s3_access_key="admin",
                s3_secret_key="adminadmin",
                bootstrap_admin_username="admin",
                bootstrap_admin_password="admin123456",
            )
        )

    message = str(exc.value)
    assert "JWT_SECRET" in message
    assert "TRUSTED_HOSTS" in message
    assert "S3_SECRET_KEY" in message


def test_validate_security_settings_accepts_hardened_production() -> None:
    validate_security_settings(_settings())


def test_validate_security_settings_skips_development() -> None:
    validate_security_settings(
        _settings(
            deployment_mode="development",
            jwt_secret="change-me-in-production",
            trusted_hosts=["*"],
            docs_enabled=True,
            scan_pass_when_unconfigured=True,
            s3_access_key="admin",
            s3_secret_key="adminadmin",
        )
    )


def test_in_memory_rate_limiter_blocks_after_threshold() -> None:
    limiter = InMemoryRateLimiter(attempts=2, window_seconds=60, block_seconds=30)

    assert limiter.retry_after("user:admin", now=100) == 0
    limiter.record_failure("user:admin", now=100)
    assert limiter.retry_after("user:admin", now=101) == 0
    limiter.record_failure("user:admin", now=102)

    assert limiter.retry_after("user:admin", now=103) == 29
    limiter.record_success("user:admin")
    assert limiter.retry_after("user:admin", now=104) == 0
