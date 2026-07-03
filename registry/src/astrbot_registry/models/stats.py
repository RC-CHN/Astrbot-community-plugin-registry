from datetime import date
import uuid
from typing import TYPE_CHECKING

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .version import PluginVersion


class PluginVersionStat(Base):
    __tablename__ = "plugin_version_stats"
    __table_args__ = (
        UniqueConstraint("version_id", "date", name="uq_version_stats_version_date"),
        CheckConstraint("download_count >= 0", name="ck_version_stats_download_count"),
        CheckConstraint("install_count >= 0", name="ck_version_stats_install_count"),
        Index("idx_version_stats_version", "version_id"),
        Index("idx_version_stats_date", "date"),
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
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    install_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)

    version: Mapped["PluginVersion"] = relationship("PluginVersion")
