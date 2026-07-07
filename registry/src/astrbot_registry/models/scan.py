from datetime import datetime
import uuid
from typing import TYPE_CHECKING

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .version import PluginVersion


class SecurityScan(Base):
    __tablename__ = "security_scans"
    __table_args__ = (
        UniqueConstraint("version_id"),
        CheckConstraint(
            "virustotal_mode IN ('pending', 'real', 'skipped', 'error')",
            name="ck_security_scans_virustotal_mode",
        ),
        CheckConstraint(
            "llm_agent_mode IN ('pending', 'real', 'skipped', 'error')",
            name="ck_security_scans_llm_agent_mode",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plugin_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    virustotal_pass: Mapped[bool | None] = mapped_column(Boolean)
    virustotal_msg: Mapped[str | None] = mapped_column(Text)
    virustotal_mode: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        server_default=text("'pending'"),
        nullable=False,
    )
    virustotal_analysis_id: Mapped[str | None] = mapped_column(Text)
    virustotal_file_sha256: Mapped[str | None] = mapped_column(String(64))
    virustotal_submitted_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True))
    virustotal_deadline_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True))
    virustotal_next_poll_at: Mapped[datetime | None] = mapped_column(pg.TIMESTAMP(timezone=True))
    virustotal_poll_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    llm_agent_pass: Mapped[bool | None] = mapped_column(Boolean)
    llm_agent_msg: Mapped[str | None] = mapped_column(Text)
    llm_agent_mode: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        server_default=text("'pending'"),
        nullable=False,
    )
    scanned_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    version: Mapped["PluginVersion"] = relationship(
        "PluginVersion",
        back_populates="scan",
    )
