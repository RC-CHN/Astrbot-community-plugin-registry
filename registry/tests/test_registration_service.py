from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from astrbot_registry.api import auth
from astrbot_registry.schemas.auth import RegisterRequest
from astrbot_registry.services import registration_service


class FakeRequest:
    headers = {}
    client = SimpleNamespace(host="127.0.0.1")


@pytest.mark.asyncio
async def test_register_config_reports_mode(monkeypatch) -> None:
    async def runtime_registration_mode(_db):
        return "invite"

    monkeypatch.setattr(auth, "runtime_registration_mode", runtime_registration_mode)

    assert await auth.register_config(db=object()) == {
        "mode": "invite",
        "pow_required": True,
        "invite_required": True,
        "approval_required": False,
    }


@pytest.mark.asyncio
async def test_pow_challenge_can_be_consumed_once(monkeypatch) -> None:
    async def no_redis():
        return None

    monkeypatch.setattr(registration_service, "get_redis", no_redis)
    monkeypatch.setattr(registration_service.settings, "registration_pow_difficulty", 8)
    challenge = await registration_service.create_pow_challenge()
    nonce = _solve_pow(challenge["challenge_id"], challenge["salt"], challenge["difficulty"])

    await registration_service.consume_pow_challenge(challenge["challenge_id"], nonce)
    with pytest.raises(registration_service.RegistrationError):
        await registration_service.consume_pow_challenge(challenge["challenge_id"], nonce)


@pytest.mark.asyncio
async def test_register_endpoint_rejects_disabled_mode(monkeypatch) -> None:
    async def consume_pow(_challenge_id, _nonce):
        return None

    async def register_user(_db, **_kwargs):
        raise registration_service.RegistrationClosedError("registration is disabled")

    monkeypatch.setattr(auth.settings, "registration_rate_limit_enabled", False)
    monkeypatch.setattr(auth, "consume_pow_challenge", consume_pow)
    monkeypatch.setattr(auth, "register_user", register_user)

    with pytest.raises(HTTPException) as exc:
        await auth.register(FakeRequest(), _register_request(), db=object())  # type: ignore[arg-type]

    assert exc.value.status_code == 403
    assert exc.value.detail == "registration is disabled"


@pytest.mark.asyncio
async def test_register_endpoint_returns_pending_approval(monkeypatch) -> None:
    async def consume_pow(_challenge_id, _nonce):
        return None

    async def fake_register_user(_db, **_kwargs):
        return SimpleNamespace(id="user-id", status="pending_approval")

    monkeypatch.setattr(auth.settings, "registration_rate_limit_enabled", False)
    monkeypatch.setattr(auth, "consume_pow_challenge", consume_pow)
    monkeypatch.setattr(auth, "register_user", fake_register_user)

    response = await auth.register(FakeRequest(), _register_request(), db=object())  # type: ignore[arg-type]

    assert response == {
        "status": "pending_approval",
        "user_id": "user-id",
        "message": "waiting for administrator approval",
    }


def _register_request() -> RegisterRequest:
    return RegisterRequest(
        username="alice",
        email="alice@example.com",
        password="strong-password",
        challenge_id="challenge-id",
        nonce="1",
    )


def _solve_pow(challenge_id: str, salt: str, difficulty: int) -> str:
    nonce = 0
    while True:
        candidate = str(nonce)
        if registration_service.verify_pow(challenge_id, salt, candidate, difficulty):
            return candidate
        nonce += 1
