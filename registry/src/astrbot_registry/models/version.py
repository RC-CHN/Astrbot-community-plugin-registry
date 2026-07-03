from datetime import datetime
from typing import Optional, TYPE_CHECKING

import uuid

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .plugin import Plugin
    from .scan import SecurityScan
    from .user import User


class PluginVersion(Base):
    __tablename__ = "plugin_versions"
    __table_args__ = (
        UniqueConstraint("plugin_id", "version"),
        CheckConstraint(
            "source_type IN ('git_auto', 'manual_upload')",
            name="ck_versions_source_type",
        ),
        CheckConstraint(
            "build_status IN ('pending', 'building', 'success', 'failed', 'scanning')",
            name="ck_versions_build_status",
        ),
        CheckConstraint(
            "version_status IN ('draft', 'active', 'deprecated', 'deleted')",
            name="ck_versions_version_status",
        ),
        CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_versions_file_size"),
        CheckConstraint(
            "build_status <> 'success' OR (s3_key IS NOT NULL AND download_url IS NOT NULL)",
            name="ck_versions_success_has_artifact",
        ),
        CheckConstraint(
            "NOT is_latest OR (version_status = 'active' AND build_status = 'success')",
            name="ck_versions_latest_active_success",
        ),
        Index(
            "idx_versions_is_latest_per_plugin",
            "plugin_id",
            unique=True,
            postgresql_where=text("is_latest = true"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    plugin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(64))
    source_type: Mapped[str] = mapped_column(
        String(32),
        default="git_auto",
        server_default=text("'git_auto'"),
        nullable=False,
    )
    download_url: Mapped[str | None] = mapped_column(String(512))
    s3_key: Mapped[str | None] = mapped_column(String(512))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    metadata_raw: Mapped[str | None] = mapped_column(Text)
    changelog: Mapped[str | None] = mapped_column(Text)
    build_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        server_default=text("'pending'"),
        nullable=False,
    )
    build_log: Mapped[str | None] = mapped_column(Text)
    version_status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        server_default=text("'draft'"),
        nullable=False,
    )
    is_latest: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
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
        onupdate=func.now(),
    )

    plugin: Mapped["Plugin"] = relationship("Plugin", back_populates="versions")
    scan: Mapped[Optional["SecurityScan"]] = relationship(
        "SecurityScan",
        back_populates="version",
        uselist=False,
    )
    creator: Mapped[Optional["User"]] = relationship("User", back_populates="versions")
