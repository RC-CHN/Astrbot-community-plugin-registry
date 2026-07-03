from datetime import datetime

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=func.now(),
    )
