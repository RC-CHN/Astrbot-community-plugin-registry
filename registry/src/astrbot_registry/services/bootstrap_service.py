"""Initial application bootstrap helpers."""

import logging

from sqlalchemy import func, select

from ..config import settings
from ..database import async_session
from ..models import User
from .auth_service import get_password_hash

logger = logging.getLogger(__name__)


async def bootstrap_admin_user() -> None:
    """Create the first admin user from environment configuration."""
    username = settings.bootstrap_admin_username.strip()
    password = settings.bootstrap_admin_password
    role = settings.bootstrap_admin_role.strip() or "admin"

    if not username or not password:
        return

    if role not in {"admin", "reviewer"}:
        logger.warning("Skipping bootstrap admin user: invalid role %r", role)
        return

    async with async_session() as db:
        count = await db.scalar(select(func.count(User.id)))
        if count and count > 0:
            return

        user = User(
            username=username,
            password_hash=get_password_hash(password),
            role=role,
        )
        db.add(user)
        await db.commit()
        logger.info("Created initial %s user %r from environment", role, username)
