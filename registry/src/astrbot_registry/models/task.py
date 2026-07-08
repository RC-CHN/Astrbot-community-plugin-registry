from datetime import datetime
import uuid
from typing import Optional, TYPE_CHECKING

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .plugin import Plugin
    from .version import PluginVersion


class WorkerTask(Base):
    __tablename__ = "worker_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'delayed', 'running', 'retrying', 'succeeded', 'failed', 'dead', 'cancelled')",
            name="ck_worker_tasks_status",
        ),
        Index("idx_worker_tasks_status_created", "status", "created_at"),
        Index("idx_worker_tasks_plugin_created", "plugin_id", "created_at"),
        Index("idx_worker_tasks_version_created", "version_id", "created_at"),
        Index("idx_worker_tasks_type_created", "task_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default="queued",
        server_default=text("'queued'"),
        nullable=False,
    )
    plugin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plugins.id", ondelete="SET NULL"))
    version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plugin_versions.id", ondelete="SET NULL"))
    provider: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default=text("3"), nullable=False)
    queued_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    started_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
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

    plugin: Mapped[Optional["Plugin"]] = relationship("Plugin")
    version: Mapped[Optional["PluginVersion"]] = relationship("PluginVersion")
