from datetime import datetime
import uuid
from typing import TYPE_CHECKING

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import CheckConstraint, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .plugin import Plugin
    from .version import PluginVersion


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('push', 'release', 'tag', 'manual')",
            name="ck_webhook_events_event_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'success', 'failed', 'ignored')",
            name="ck_webhook_events_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plugin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"),
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict | None] = mapped_column(pg.JSONB)
    triggered_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plugin_versions.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    plugin: Mapped["Plugin | None"] = relationship("Plugin")
    triggered_version: Mapped["PluginVersion | None"] = relationship("PluginVersion")
