from contextlib import asynccontextmanager

import psycopg
import psycopg_pool
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.auth import install_auth
from app.db import get_pool
from app.routes import places
from app.settings import Settings


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.pool.close()

    hidden = {"docs_url": None, "redoc_url": None, "openapi_url": None} if settings.env == "production" else {}
    app = FastAPI(title="SunHaEat API", lifespan=lifespan, **hidden)
    app.state.settings = settings
    app.state.pool = get_pool(settings)
    install_auth(app)

    async def database_unavailable(_request, _error) -> JSONResponse:
        return JSONResponse({"detail": "database_unavailable"}, 503)

    for error in (psycopg.OperationalError, psycopg_pool.PoolTimeout, psycopg_pool.PoolClosed):
        app.add_exception_handler(error, database_unavailable)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(places.router)
    return app
