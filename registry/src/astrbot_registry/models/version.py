from datetime import datetime
from typing import Optional, TYPE_CHECKING

import uuid

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .plugin import Plugin
    from .scan import SecurityScan
    from .user import User


class PluginVersion(Base):
    __tablename__ = "plugin_versions"
    __table_args__ = (UniqueConstraint("plugin_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plugin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(String(32), default="git_auto")
    download_url: Mapped[str | None] = mapped_column(String(512))
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    metadata_raw: Mapped[str | None] = mapped_column(Text)
    changelog: Mapped[str | None] = mapped_column(Text)
    build_status: Mapped[str] = mapped_column(String(50), default="pending")
    build_log: Mapped[str | None] = mapped_column(Text)
    version_status: Mapped[str] = mapped_column(String(50), default="draft")
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
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

    plugin: Mapped["Plugin"] = relationship("Plugin", back_populates="versions")
    scan: Mapped[Optional["SecurityScan"]] = relationship(
        "SecurityScan",
        back_populates="version",
        uselist=False,
    )
    creator: Mapped[Optional["User"]] = relationship("User", back_populates="versions")
