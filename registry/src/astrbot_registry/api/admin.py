from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)) -> dict:
    # TODO: implement admin stats
    return {"total_plugins": 0, "pending_plugins": 0}
