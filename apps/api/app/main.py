from contextlib import asynccontextmanager

import psycopg
import psycopg_pool
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.auth import install_auth
from app.chat.gemini import SdkTransport, Transport
from app.db import get_pool
from app.routes import chat, internal, places
from app.settings import Settings


def create_app(settings: Settings, transport: Transport | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.pool.close()

    hidden = {"docs_url": None, "redoc_url": None, "openapi_url": None} if settings.env == "production" else {}
    app = FastAPI(title="SunHaEat API", lifespan=lifespan, **hidden)
    app.state.settings = settings
    app.state.pool = get_pool(settings)
    if transport is None and settings.ai_ready:
        transport = SdkTransport(settings.gemini_api_key, settings.gemini_model, settings.ai_timeout_s)
    app.state.transport = transport
    install_auth(app)

    async def database_unavailable(_request, _error) -> JSONResponse:
        return JSONResponse({"detail": "database_unavailable"}, 503)

    for error in (psycopg.OperationalError, psycopg_pool.PoolTimeout, psycopg_pool.PoolClosed):
        app.add_exception_handler(error, database_unavailable)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    for module in (places, chat, internal):
        app.include_router(module.router)
    return app
