from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .api.router import api_router
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init external resources on startup."""
    if settings.s3_auto_create_bucket:
        import asyncio
        from .services.s3_service import ensure_bucket_exists

        await asyncio.to_thread(ensure_bucket_exists)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AstrBot Community Plugin Registry",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.include_router(api_router)
    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "astrbot_registry.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
