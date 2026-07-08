from datetime import datetime
import uuid

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class PluginSubmissionRequest(Base):
    __tablename__ = "plugin_submission_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review', 'accepted', 'rejected', 'duplicate')",
            name="ck_plugin_submission_requests_status",
        ),
        CheckConstraint(
            "ref_type IN ('default', 'branch', 'tag', 'commit')",
            name="ck_plugin_submission_requests_ref_type",
        ),
        Index("idx_submission_requests_status_created", "status", "created_at"),
        Index("idx_submission_requests_user_created", "user_id", "created_at"),
        Index("idx_submission_requests_repo", "repo_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    repo_url: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="github", server_default=text("'github'"), nullable=False)
    ref_type: Mapped[str] = mapped_column(String(32), default="default", server_default=text("'default'"), nullable=False)
    ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending_review",
        server_default=text("'pending_review'"),
        nullable=False,
    )
    resolved_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accepted_plugin_id: Mapped[uuid.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("plugins.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_version_id: Mapped[uuid.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("plugin_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        pg.UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True), nullable=True)
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
