"""Public authentication schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


RegistrationMode = Literal["disabled", "invite", "approval"]


class RegistrationConfigResponse(BaseModel):
    mode: RegistrationMode
    pow_required: bool = True
    invite_required: bool = False
    approval_required: bool = False


class RegisterChallengeResponse(BaseModel):
    challenge_id: str
    salt: str
    difficulty: int
    algorithm: str = "sha256-leading-zero-bits"
    expires_at: datetime


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=12, max_length=1024)
    invite_code: str | None = Field(default=None, max_length=255)
    challenge_id: str = Field(..., min_length=1, max_length=100)
    nonce: str = Field(..., min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("username is required")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("invalid email")
        return value


class RegisterResponse(BaseModel):
    status: Literal["active", "pending_approval"]
    user_id: str
    message: str


class CurrentUserResponse(BaseModel):
    id: str
    username: str
    email: str | None = None
    role: str
    status: str
