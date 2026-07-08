"""Application security hardening helpers."""

from __future__ import annotations

import math
import ipaddress
import hashlib
import threading
import time
from dataclasses import dataclass

from fastapi import Request

from ..config import Settings, settings

DEFAULT_JWT_SECRET = "change-me-in-production"
DEFAULT_BOOTSTRAP_PASSWORD = "admin123456"
DEFAULT_S3_ACCESS_KEY = "admin"
DEFAULT_S3_SECRET_KEY = "adminadmin"


class SecurityConfigurationError(RuntimeError):
    """Raised when production security settings are unsafe."""


def is_production(app_settings: Settings = settings) -> bool:
    return app_settings.deployment_mode.strip().lower() in {"prod", "production"}


def validate_security_settings(app_settings: Settings = settings) -> None:
    """Fail fast when production mode still uses development-safe defaults."""
    if not is_production(app_settings):
        return

    errors: list[str] = []
    if _is_weak_secret(app_settings.jwt_secret, DEFAULT_JWT_SECRET, min_length=32):
        errors.append("JWT_SECRET must be changed and at least 32 characters long")
    if _contains_wildcard(app_settings.trusted_hosts):
        errors.append("TRUSTED_HOSTS must be set to the public domain/IP, not '*'")
    if "*" in app_settings.cors_allow_origins:
        errors.append("CORS_ALLOW_ORIGINS must not contain '*' in production")
    if app_settings.docs_enabled:
        errors.append("DOCS_ENABLED must be false in production")
    if app_settings.bootstrap_api_enabled:
        errors.append("BOOTSTRAP_API_ENABLED must be false in production")
    if not app_settings.github_webhook_require_secret:
        errors.append("GITHUB_WEBHOOK_REQUIRE_SECRET must stay true in production")
    if _is_weak_secret(app_settings.s3_secret_key, DEFAULT_S3_SECRET_KEY, min_length=16):
        errors.append("S3_SECRET_KEY must be changed and at least 16 characters long")
    if app_settings.s3_access_key == DEFAULT_S3_ACCESS_KEY:
        errors.append("S3_ACCESS_KEY must be changed from the development default")

    if app_settings.bootstrap_admin_username or app_settings.bootstrap_admin_password:
        if _is_weak_secret(
            app_settings.bootstrap_admin_password,
            DEFAULT_BOOTSTRAP_PASSWORD,
            min_length=12,
        ):
            errors.append(
                "BOOTSTRAP_ADMIN_PASSWORD must be changed and at least 12 characters long"
            )

    if errors:
        joined = "; ".join(errors)
        raise SecurityConfigurationError(f"Unsafe production configuration: {joined}")


def _is_weak_secret(value: str, default: str, *, min_length: int) -> bool:
    return not value or value == default or len(value) < min_length


def _contains_wildcard(values: list[str]) -> bool:
    return not values or "*" in values


@dataclass
class _RateLimitState:
    attempts: int
    window_started_at: float
    blocked_until: float = 0


class InMemoryRateLimiter:
    """Small per-process fixed-window limiter for authentication endpoints."""

    def __init__(
        self,
        *,
        attempts: int,
        window_seconds: int,
        block_seconds: int,
    ) -> None:
        self.attempts = max(1, attempts)
        self.window_seconds = max(1, window_seconds)
        self.block_seconds = max(1, block_seconds)
        self._states: dict[str, _RateLimitState] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str, *, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        with self._lock:
            state = self._states.get(key)
            if state is None:
                return 0
            if state.blocked_until > now:
                return max(1, math.ceil(state.blocked_until - now))
            if now - state.window_started_at > self.window_seconds:
                self._states.pop(key, None)
            return 0

    def record_failure(self, key: str, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            state = self._states.get(key)
            if state is None or now - state.window_started_at > self.window_seconds:
                state = _RateLimitState(attempts=0, window_started_at=now)
            state.attempts += 1
            if state.attempts >= self.attempts:
                state.blocked_until = now + self.block_seconds
            self._states[key] = state

    def record_success(self, key: str) -> None:
        with self._lock:
            self._states.pop(key, None)


login_rate_limiter = InMemoryRateLimiter(
    attempts=settings.login_rate_limit_attempts,
    window_seconds=settings.login_rate_limit_window_seconds,
    block_seconds=settings.login_rate_limit_block_seconds,
)

registration_challenge_rate_limiter = InMemoryRateLimiter(
    attempts=settings.registration_challenge_rate_limit_attempts,
    window_seconds=settings.registration_challenge_rate_limit_window_seconds,
    block_seconds=settings.registration_challenge_rate_limit_block_seconds,
)

registration_submit_rate_limiter = InMemoryRateLimiter(
    attempts=settings.registration_submit_rate_limit_attempts,
    window_seconds=settings.registration_submit_rate_limit_window_seconds,
    block_seconds=settings.registration_submit_rate_limit_block_seconds,
)


def login_rate_limit_keys(request: Request, username: str) -> list[str]:
    username_key = username.strip().lower() or "<empty>"
    client_ip = _client_ip(request)
    return [f"user:{username_key}", f"ip:{client_ip}"]


def registration_challenge_rate_limit_key(request: Request) -> str:
    return f"register-challenge:ip:{_client_ip(request)}"


def registration_submit_rate_limit_keys(
    request: Request,
    *,
    username: str,
    email: str,
    invite_code: str | None = None,
) -> list[str]:
    keys = [
        f"register-submit:ip:{_client_ip(request)}",
        f"register-submit:username:{_hash_key(username.strip().lower())}",
        f"register-submit:email:{_hash_key(email.strip().lower())}",
    ]
    if invite_code:
        keys.append(f"register-submit:invite:{_hash_key(invite_code.strip())}")
    return keys


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _client_ip(request: Request, app_settings: Settings = settings) -> str:
    peer = _peer_ip(request)
    if app_settings.trust_proxy_headers and _is_trusted_proxy(peer, app_settings.trusted_proxy_cidrs):
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip() or peer
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip() or peer
    return peer


def _peer_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _is_trusted_proxy(peer: str, trusted_cidrs: list[str]) -> bool:
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return False

    for cidr in trusted_cidrs:
        try:
            network = _parse_proxy_network(cidr)
        except ValueError:
            continue
        if peer_ip in network:
            return True
    return False


def _parse_proxy_network(value: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    value = value.strip()
    if "/" in value:
        return ipaddress.ip_network(value, strict=False)
    ip = ipaddress.ip_address(value)
    prefix = 32 if ip.version == 4 else 128
    return ipaddress.ip_network(f"{value}/{prefix}", strict=False)
