import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from testsupport.api import SECRET, SignedClient


@pytest.fixture
def client():
    return TestClient(create_app(Settings(_env_file=None)))


def test_liveness_needs_no_database(client):
    assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize("flag,key,model,ready", [
    ("true", "k", "", False),
    ("true", "", "m", False),
    ("yes", "k", "m", False),
    ("TRUE", "k", "m", False),
    ("true", "k", "m", True),
])
def test_ai_is_off_unless_fully_configured(flag, key, model, ready):
    s = Settings(_env_file=None, ai_enabled=flag, gemini_api_key=key, gemini_model=model)
    assert s.ai_ready is ready


@pytest.mark.parametrize("path", ["/docs", "/openapi.json", "/redoc"])
def test_api_docs_are_hidden_in_production(path):
    prod = SignedClient(create_app(Settings(_env_file=None, env="production", api_hmac_secret=SECRET)))
    assert prod.get(path).status_code == 404
