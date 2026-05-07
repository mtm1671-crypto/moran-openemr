import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api import initialize_phi_storage, router
from app.config import get_settings
from app.scheduler import nightly_maintenance_loop


def create_app() -> FastAPI:
    settings = get_settings()
    # Config validation is part of startup. Unsafe PHI/provider/storage settings
    # fail before the API can serve requests.
    settings.assert_runtime_config()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await initialize_phi_storage(settings)
        maintenance_task: asyncio.Task[None] | None = None
        if settings.nightly_maintenance_enabled:
            # Single-service demo can run maintenance in-process. Production can
            # move the same logic to the Railway worker/cron service.
            maintenance_task = asyncio.create_task(nightly_maintenance_loop(settings))
        try:
            yield
        finally:
            if maintenance_task is not None:
                maintenance_task.cancel()
                try:
                    await maintenance_task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title="AgentForge Clinical Co-Pilot API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.public_base_url],
        allow_origin_regex=_local_cors_origin_regex(settings.app_env),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.middleware("http")
    async def security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if settings.requires_phi_controls():
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
    return app


def _local_cors_origin_regex(app_env: str) -> str | None:
    if app_env != "local":
        return None
    return r"https?://(localhost|127\.0\.0\.1):\d+"


app = create_app()
