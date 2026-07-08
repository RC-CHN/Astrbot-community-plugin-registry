from fastapi import APIRouter

from .auth import auth_router
from .admin import admin_router
from .public import public_router
from .submissions import submissions_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(public_router)
api_router.include_router(auth_router)
api_router.include_router(submissions_router)
api_router.include_router(admin_router)
