from datetime import datetime
import uuid
from typing import TYPE_CHECKING

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Boolean, ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .version import PluginVersion


class SecurityScan(Base):
    __tablename__ = "security_scans"

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plugin_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    virustotal_pass: Mapped[bool | None] = mapped_column(Boolean)
    virustotal_msg: Mapped[str | None] = mapped_column(Text)
    llm_agent_pass: Mapped[bool | None] = mapped_column(Boolean)
    llm_agent_msg: Mapped[str | None] = mapped_column(Text)
    scanned_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    version: Mapped["PluginVersion"] = relationship(
        "PluginVersion",
        back_populates="scan",
    )
