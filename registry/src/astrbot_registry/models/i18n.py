import uuid
from typing import TYPE_CHECKING

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .plugin import Plugin


class PluginI18n(Base):
    __tablename__ = "plugin_i18n"
    __table_args__ = (UniqueConstraint("plugin_id", "locale"),)

    id: Mapped[uuid.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    plugin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    data: Mapped[dict] = mapped_column(pg.JSONB, nullable=False, default=dict)

    plugin: Mapped["Plugin"] = relationship("Plugin", back_populates="i18n_entries")
