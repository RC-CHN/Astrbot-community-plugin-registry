from datetime import datetime
import uuid

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class UserInvite(Base):
    __tablename__ = "user_invites"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'disabled')", name="ck_user_invites_status"),
        CheckConstraint("max_uses > 0", name="ck_user_invites_max_uses_positive"),
        CheckConstraint("used_count >= 0", name="ck_user_invites_used_count_nonnegative"),
        CheckConstraint("used_count <= max_uses", name="ck_user_invites_used_count_lte_max"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        server_default=text("'active'"),
        nullable=False,
    )
    max_uses: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"), nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
