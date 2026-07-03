"""Download and install statistics services."""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import PluginVersionStat


async def increment_download_count(
    db: AsyncSession,
    version_id: uuid.UUID,
    stat_date: date | None = None,
) -> None:
    """Increment daily download count for a version."""
    stat_date = stat_date or date.today()
    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = pg_insert(PluginVersionStat).values(
            version_id=version_id,
            date=stat_date,
            download_count=1,
            install_count=0,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_version_stats_version_date",
            set_={
                "download_count": PluginVersionStat.download_count + 1,
            },
        )
        await db.execute(stmt)
    else:
        result = await db.execute(
            select(PluginVersionStat)
            .where(PluginVersionStat.version_id == version_id)
            .where(PluginVersionStat.date == stat_date)
        )
        stat = result.scalar_one_or_none()
        if stat is None:
            db.add(
                PluginVersionStat(
                    version_id=version_id,
                    date=stat_date,
                    download_count=1,
                    install_count=0,
                )
            )
        else:
            stat.download_count += 1
    await db.commit()


async def increment_install_count(
    db: AsyncSession,
    version_id: uuid.UUID,
    stat_date: date | None = None,
) -> None:
    """Increment daily install count for a version."""
    stat_date = stat_date or date.today()
    if db.bind and db.bind.dialect.name == "postgresql":
        stmt = pg_insert(PluginVersionStat).values(
            version_id=version_id,
            date=stat_date,
            download_count=0,
            install_count=1,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_version_stats_version_date",
            set_={
                "install_count": PluginVersionStat.install_count + 1,
            },
        )
        await db.execute(stmt)
    else:
        result = await db.execute(
            select(PluginVersionStat)
            .where(PluginVersionStat.version_id == version_id)
            .where(PluginVersionStat.date == stat_date)
        )
        stat = result.scalar_one_or_none()
        if stat is None:
            db.add(
                PluginVersionStat(
                    version_id=version_id,
                    date=stat_date,
                    download_count=0,
                    install_count=1,
                )
            )
        else:
            stat.install_count += 1
    await db.commit()
