import json
import pathlib
import time

import pytest
from fastapi.testclient import TestClient

from app.auth import sign
from app.main import create_app
from app.settings import Settings

VECTORS = json.loads((pathlib.Path(__file__).parents[3] / "tests/fixtures/hmac.json").read_text(encoding="utf8"))


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: v["name"])
def test_signature_matches_shared_vectors(v):
    assert sign(v["secret"], v["ts"], v["method"], v["target"], v["session"], v["ip"], v["body"].encode()) == v["signature"]


def test_signed_request_is_accepted(api):
    assert api.get("/v1/places").status_code == 200


def test_missing_signature_is_401(api):
    assert api.http.get("/v1/places").status_code == 401


@pytest.mark.parametrize("offset", [-61, 61])
def test_stale_or_future_signature_is_401(api, offset):
    h = api.headers("GET", "/v1/places", ts=int(time.time()) + offset)
    assert api.http.get("/v1/places", headers=h).status_code == 401


@pytest.mark.parametrize("header,value", [
    ("X-SHE-Session", "someone-else"), ("X-SHE-IP", "other-ip"), ("X-SHE-Signature", "0" * 64),
    ("X-SHE-Timestamp", "abc"), ("X-SHE-Signature", "ไม่ใช่".encode()),
])
def test_tampered_header_is_401(api, header, value):
    h = api.headers("GET", "/v1/places") | {header: value}
    assert api.http.get("/v1/places", headers=h).status_code == 401


def test_signature_covers_query_and_body(api):
    h = api.headers("GET", "/v1/places?tag=isan")
    assert api.http.get("/v1/places?tag=noodle", headers=h).status_code == 401
    h = api.headers("POST", "/v1/places", b"{}")
    assert api.http.post("/v1/places", content=b"[]", headers=h).status_code == 401


def test_unknown_path_is_401_without_signature(api):
    assert api.http.get("/v1/nope").status_code == 401


def test_large_body_is_413(api):
    assert api.http.post("/v1/places", content=b"x" * 16385).status_code == 413


def test_missing_server_secret_fails_closed():
    c = TestClient(create_app(Settings(_env_file=None)))
    assert c.get("/v1/places").status_code == 503 and c.get("/healthz").status_code == 200
