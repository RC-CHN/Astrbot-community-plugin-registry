"""Public user registration and proof-of-work helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cache import get_redis
from ..config import settings
from ..models import User, UserInvite
from .auth_service import get_password_hash
from .runtime_config import normalize_registration_mode, runtime_registration_mode

_challenge_prefix = "registration_challenge:"
_memory_challenges: dict[str, dict[str, object]] = {}
_memory_challenge_lock = threading.Lock()


class RegistrationError(ValueError):
    """Raised when a public registration request is rejected."""


class RegistrationClosedError(RegistrationError):
    """Raised when public registration is disabled."""


def registration_mode() -> str:
    return normalize_registration_mode(settings.user_registration_mode)


async def create_pow_challenge() -> dict[str, object]:
    challenge_id = str(uuid.uuid4())
    salt = secrets.token_hex(16)
    ttl = max(30, settings.registration_pow_challenge_ttl_seconds)
    expires_at = datetime.fromtimestamp(time.time() + ttl, tz=timezone.utc)
    payload = {
        "salt": salt,
        "difficulty": max(1, settings.registration_pow_difficulty),
        "expires_at": expires_at.isoformat(),
    }
    redis = await get_redis()
    if redis is not None:
        await redis.setex(_challenge_prefix + challenge_id, ttl, json.dumps(payload))
    else:
        with _memory_challenge_lock:
            _cleanup_memory_challenges()
            _memory_challenges[challenge_id] = payload
    return {
        "challenge_id": challenge_id,
        "salt": salt,
        "difficulty": payload["difficulty"],
        "expires_at": expires_at,
    }


async def consume_pow_challenge(challenge_id: str, nonce: str) -> None:
    payload = await _pop_challenge(challenge_id)
    if payload is None:
        raise RegistrationError("registration rejected")
    try:
        salt = str(payload["salt"])
        difficulty = int(payload["difficulty"])
        expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise RegistrationError("registration rejected") from exc
    if expires_at < datetime.now(timezone.utc):
        raise RegistrationError("registration rejected")
    if not verify_pow(challenge_id, salt, nonce, difficulty):
        raise RegistrationError("registration rejected")


def verify_pow(challenge_id: str, salt: str, nonce: str, difficulty: int) -> bool:
    digest = hashlib.sha256(f"{challenge_id}:{salt}:{nonce}".encode("utf-8")).digest()
    return _leading_zero_bits(digest) >= difficulty


def _leading_zero_bits(data: bytes) -> int:
    bits = 0
    for byte in data:
        if byte == 0:
            bits += 8
            continue
        return bits + (8 - byte.bit_length())
    return bits


async def register_user(
    db: AsyncSession,
    *,
    username: str,
    email: str,
    password: str,
    invite_code: str | None,
) -> User:
    mode = await runtime_registration_mode(db)
    if mode == "disabled":
        raise RegistrationClosedError("registration is disabled")

    normalized_username = username.strip()
    normalized_email = email.strip().lower()
    await _ensure_user_unique(db, normalized_username, normalized_email)

    invite: UserInvite | None = None
    if mode == "invite":
        if not invite_code:
            raise RegistrationError("registration rejected")
        invite = await _get_usable_invite(db, invite_code)
        if invite is None:
            raise RegistrationError("registration rejected")

    user = User(
        username=normalized_username,
        email=normalized_email,
        password_hash=get_password_hash(password),
        role="user",
        status="active" if mode == "invite" else "pending_approval",
        is_active=True,
    )
    db.add(user)
    if invite is not None:
        invite.used_count += 1
    await db.commit()
    await db.refresh(user)
    return user


def invite_code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def generate_invite_code() -> str:
    return secrets.token_urlsafe(24)


async def create_invite(
    db: AsyncSession,
    *,
    created_by: uuid.UUID | None,
    code: str | None = None,
    max_uses: int = 1,
    expires_at: datetime | None = None,
    note: str | None = None,
) -> tuple[UserInvite, str]:
    plain_code = code or generate_invite_code()
    invite = UserInvite(
        code_hash=invite_code_hash(plain_code),
        max_uses=max(1, max_uses),
        expires_at=expires_at,
        note=note,
        created_by=created_by,
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite, plain_code


async def _ensure_user_unique(db: AsyncSession, username: str, email: str) -> None:
    result = await db.execute(
        select(User).where((User.username == username) | (User.email == email))
    )
    if result.scalar_one_or_none() is not None:
        raise RegistrationError("registration rejected")


async def _get_usable_invite(db: AsyncSession, code: str) -> UserInvite | None:
    result = await db.execute(
        select(UserInvite).where(UserInvite.code_hash == invite_code_hash(code))
    )
    invite = result.scalar_one_or_none()
    if invite is None or invite.status != "active":
        return None
    if invite.used_count >= invite.max_uses:
        return None
    if invite.expires_at is not None and invite.expires_at < datetime.now(timezone.utc):
        return None
    return invite


async def _pop_challenge(challenge_id: str) -> dict[str, object] | None:
    redis = await get_redis()
    key = _challenge_prefix + challenge_id
    if redis is not None:
        raw = await redis.get(key)
        if raw is not None:
            await redis.delete(key)
            return json.loads(raw)
        return None
    with _memory_challenge_lock:
        _cleanup_memory_challenges()
        return _memory_challenges.pop(challenge_id, None)


def _cleanup_memory_challenges() -> None:
    now = datetime.now(timezone.utc)
    expired = []
    for challenge_id, payload in _memory_challenges.items():
        try:
            expires_at = datetime.fromisoformat(str(payload["expires_at"]))
        except (KeyError, ValueError, TypeError):
            expired.append(challenge_id)
            continue
        if expires_at < now:
            expired.append(challenge_id)
    for challenge_id in expired:
        _memory_challenges.pop(challenge_id, None)
