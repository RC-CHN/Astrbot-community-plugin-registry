import uuid
from datetime import timedelta

from astrbot_registry.services.auth_service import (
    create_access_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from astrbot_registry.models import User


def test_password_hash() -> None:
    password = "secret123"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


def test_token_encode_decode() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, expires_delta=timedelta(minutes=5))
    decoded = decode_token(token)
    assert decoded == user_id


def test_decode_invalid_token() -> None:
    assert decode_token("not-a-valid-token") is None


def test_inactive_user_model_flag() -> None:
    user = User(username="disabled", password_hash="hash", role="reviewer", is_active=False)
    assert user.is_active is False
