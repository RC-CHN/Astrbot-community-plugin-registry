from contextlib import asynccontextmanager
import asyncio

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .api.router import api_router
from .config import settings
from .services.errors import RegistryError
from .services.security_service import validate_security_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init external resources on startup."""
    from .services.bootstrap_service import bootstrap_admin_user
    from .services.migration_service import run_database_migrations

    validate_security_settings()

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
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    configure_middlewares(app)
    app.include_router(api_router)

    @app.exception_handler(RegistryError)
    async def registry_error_handler(request: Request, exc: RegistryError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc)},
        )

    return app


def configure_middlewares(app: FastAPI) -> None:
    trusted_hosts = [host for host in settings.trusted_hosts if host]
    if trusted_hosts and "*" not in trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    cors_origins = [origin for origin in settings.cors_allow_origins if origin]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    if settings.security_headers_enabled:

        @app.middleware("http")
        async def security_headers_middleware(request: Request, call_next):
            response = await call_next(request)
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=()",
            )
            response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
            if settings.hsts_enabled:
                response.headers.setdefault(
                    "Strict-Transport-Security",
                    f"max-age={settings.hsts_max_age_seconds}; includeSubDomains",
                )
            return response


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
