import uuid
from typing import TYPE_CHECKING

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import ARRAY, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .i18n import PluginI18n
    from .tag import Tag
    from .version import PluginVersion


class Plugin(Base):
    __tablename__ = "plugins"

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plugin_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(512), nullable=False)
    social_link: Mapped[str | None] = mapped_column(String(512))
    category: Mapped[str | None] = mapped_column(String(100))
    logo_s3_key: Mapped[str | None] = mapped_column(String(512))
    stars: Mapped[int] = mapped_column(Integer, default=0)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    support_platforms: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    astrbot_version: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="pending")

    created_at: Mapped[pg.TIMESTAMP] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=pg.text("now()"),
    )
    updated_at: Mapped[pg.TIMESTAMP] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=pg.text("now()"),
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
