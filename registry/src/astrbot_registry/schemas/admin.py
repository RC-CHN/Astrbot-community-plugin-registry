"""Admin-related Pydantic schemas."""

from pydantic import BaseModel


class AdminStatsResponse(BaseModel):
    total_plugins: int
    pending_plugins: int
