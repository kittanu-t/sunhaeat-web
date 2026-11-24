from fastapi import FastAPI

from app.settings import Settings


def create_app(settings: Settings) -> FastAPI:
    hidden = {"docs_url": None, "redoc_url": None, "openapi_url": None} if settings.env == "production" else {}
    app = FastAPI(title="SunHaEat API", **hidden)
    app.state.settings = settings

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
