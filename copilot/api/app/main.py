from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AgentForge Clinical Co-Pilot API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.public_base_url],
        allow_origin_regex=_local_cors_origin_regex(settings.app_env),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


def _local_cors_origin_regex(app_env: str) -> str | None:
    if app_env != "local":
        return None
    return r"https?://(localhost|127\.0\.0\.1):\d+"


app = create_app()
