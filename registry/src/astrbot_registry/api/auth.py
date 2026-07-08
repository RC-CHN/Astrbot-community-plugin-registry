"""Public authentication endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.deps import get_current_user, get_db
from ..models import User
from ..config import settings
from ..schemas.auth import (
    RegisterChallengeResponse,
    CurrentUserResponse,
    RegisterRequest,
    RegisterResponse,
    RegistrationConfigResponse,
)
from ..services.registration_service import (
    RegistrationClosedError,
    RegistrationError,
    consume_pow_challenge,
    create_pow_challenge,
    register_user,
)
from ..services.runtime_config import runtime_registration_mode
from ..services.security_service import (
    registration_challenge_rate_limit_key,
    registration_challenge_rate_limiter,
    registration_submit_rate_limit_keys,
    registration_submit_rate_limiter,
)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.get("/register/config", response_model=RegistrationConfigResponse)
async def register_config(db: AsyncSession = Depends(get_db)) -> dict:
    mode = await runtime_registration_mode(db)
    return {
        "mode": mode,
        "pow_required": True,
        "invite_required": mode == "invite",
        "approval_required": mode == "approval",
    }


@auth_router.get("/me", response_model=CurrentUserResponse)
async def current_user(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "status": user.status,
    }


@auth_router.get("/register/challenge", response_model=RegisterChallengeResponse)
async def register_challenge(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    if await runtime_registration_mode(db) == "disabled":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="registration is disabled")
    if settings.registration_rate_limit_enabled:
        key = registration_challenge_rate_limit_key(request)
        retry_after = registration_challenge_rate_limiter.retry_after(key)
        if retry_after > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many registration attempts",
                headers={"Retry-After": str(retry_after)},
            )
        registration_challenge_rate_limiter.record_failure(key)
    return await create_pow_challenge()


@auth_router.post("/register", response_model=RegisterResponse)
async def register(
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    rate_limit_keys = registration_submit_rate_limit_keys(
        request,
        username=data.username,
        email=data.email,
        invite_code=data.invite_code,
    )
    if settings.registration_rate_limit_enabled:
        retry_after = max(registration_submit_rate_limiter.retry_after(key) for key in rate_limit_keys)
        if retry_after > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many registration attempts",
                headers={"Retry-After": str(retry_after)},
            )

    try:
        await consume_pow_challenge(data.challenge_id, data.nonce)
        user = await register_user(
            db,
            username=data.username,
            email=data.email,
            password=data.password,
            invite_code=data.invite_code,
        )
    except RegistrationClosedError as exc:
        _record_registration_failure(rate_limit_keys)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RegistrationError as exc:
        _record_registration_failure(rate_limit_keys)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="registration rejected") from exc

    for key in rate_limit_keys:
        registration_submit_rate_limiter.record_success(key)
    return {
        "status": user.status,
        "user_id": str(user.id),
        "message": "registered" if user.status == "active" else "waiting for administrator approval",
    }


def _record_registration_failure(keys: list[str]) -> None:
    if not settings.registration_rate_limit_enabled:
        return
    for key in keys:
        registration_submit_rate_limiter.record_failure(key)
