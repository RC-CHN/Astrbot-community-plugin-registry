from contextlib import asynccontextmanager
import asyncio

import uvicorn
from fastapi import Request
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .api.router import api_router
from .config import settings
from .services.errors import RegistryError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init external resources on startup."""
    from .services.bootstrap_service import bootstrap_admin_user
    from .services.migration_service import run_database_migrations

    await asyncio.to_thread(run_database_migrations)

    await bootstrap_admin_user()

    if settings.s3_auto_create_bucket:
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

    @app.exception_handler(RegistryError)
    async def registry_error_handler(request: Request, exc: RegistryError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc)},
        )

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "astrbot_registry.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_reload,
    )


if __name__ == "__main__":
    main()
