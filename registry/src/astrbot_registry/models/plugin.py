import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import ARRAY, Boolean, CheckConstraint, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .i18n import PluginI18n
    from .tag import Tag
    from .version import PluginVersion


class Plugin(Base):
    __tablename__ = "plugins"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'active', 'disabled', 'deleted')",
            name="ck_plugins_status",
        ),
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'skipped', 'rejected')",
            name="ck_plugins_review_status",
        ),
        CheckConstraint("stars >= 0", name="ck_plugins_stars_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    plugin_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_url: Mapped[str | None] = mapped_column(String(512))
    social_link: Mapped[str | None] = mapped_column(String(512))
    category: Mapped[str | None] = mapped_column(String(100))
    logo_s3_key: Mapped[str | None] = mapped_column(String(512))
    stars: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    support_platforms: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    astrbot_version: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        server_default=text("'pending'"),
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        server_default=text("'pending'"),
        nullable=False,
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
        onupdate=func.now(),
    )

    versions: Mapped[list["PluginVersion"]] = relationship(
        "PluginVersion",
        back_populates="plugin",
        cascade="all, delete-orphan",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="plugin_tags",
        back_populates="plugins",
    )
    i18n_entries: Mapped[list["PluginI18n"]] = relationship(
        "PluginI18n",
        back_populates="plugin",
        cascade="all, delete-orphan",
    )
