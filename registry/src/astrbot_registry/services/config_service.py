"""System configuration key-value service."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import SystemConfig


async def list_config(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(SystemConfig))
    return {item.key: item.value for item in result.scalars().all()}


async def update_config(db: AsyncSession, values: dict[str, str]) -> dict[str, str]:
    for key, value in values.items():
        item = await db.get(SystemConfig, key)
        if item is None:
            db.add(SystemConfig(key=key, value=value))
        else:
            item.value = value
    await db.commit()
    return await list_config(db)
