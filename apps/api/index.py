"""ASGI entry point for hosting."""
from app.main import create_app
from app.settings import Settings

app = create_app(Settings())
