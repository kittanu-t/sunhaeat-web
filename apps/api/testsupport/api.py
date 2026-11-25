"""Signed test client and a small catalog."""
import hashlib
import json
import time
import uuid
from urllib.parse import unquote, urlencode

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.auth import sign, signed_target
from app.main import create_app
from app.search.normalize import normalize_name
from app.settings import Settings

SECRET = "test-hmac-secret-32-characters-min"
SESSION = "session-hash-1"
IP = "ip-hash-1"


def add_place(db, name, *, province="TH-40", tags=(), lat=16.43, lon=102.83, price=(None, None), demo=False, confidence=0.9, **kw):
    slug = kw.get("slug") or f"p-{uuid.uuid4().hex[:8]}"
    db.execute("insert into app.provinces values (%s, %s) on conflict do nothing", [province, f"จังหวัด {province}"])
    pid = uuid.uuid5(uuid.NAMESPACE_URL, slug)
    db.execute(
        """insert into app.restaurants (id, slug, name, name_normalized, province_code, location, tags, price_min, price_max,
             confidence, is_demo, dataset_release, description)
           values (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, %s, %s, %s, 'test', %s)""",
        [pid, slug, name, normalize_name(name), province, lon, lat, list(tags), *price, confidence, demo, kw.get("description")])
    db.execute("insert into app.restaurant_sources values (%s, 'meta', %s, 'CDLA-Permissive-2.0')", [pid, slug])
    return slug


class SignedClient:
    def __init__(self, app, session=SESSION, ip=IP):
        self.http, self.session, self.ip = TestClient(app, raise_server_exceptions=False), session, ip

    def headers(self, method, target, body=b"", *, ts=None, session=None, ip=None):
        ts = str(int(time.time()) if ts is None else ts)
        session, ip = session or self.session, ip or self.ip
        return {"X-SHE-Timestamp": ts, "X-SHE-Session": session, "X-SHE-IP": ip,
                "X-SHE-Signature": sign(SECRET, ts, method, target, session, ip, body)}

    def get(self, path, **params):
        query = "?" + urlencode(params) if params else ""
        return self.http.get(path + query, headers=self.headers("GET", signed_target(unquote(path), query[1:].encode())))

    def post(self, path, payload):
        body = json.dumps(payload).encode()
        return self.http.post(path, content=body, headers=self.headers("POST", path, body) | {"content-type": "application/json"})

    def places(self, **params):
        r = self.get("/v1/places", **params)
        assert r.status_code == 200, r.text
        return r.json()["places"]


@pytest.fixture(scope="session")
def runtime_url(migrated_url):
    """Connect as the same least-privilege role production uses."""
    password = hashlib.sha256(b"test").hexdigest()
    with psycopg.connect(migrated_url, autocommit=True) as c:
        c.execute(f"alter role api_runtime login password '{password}'")
        info = c.info
        return f"postgresql://api_runtime:{password}@{info.host}:{info.port}/{info.dbname}"


@pytest.fixture
def settings(runtime_url):
    return Settings(_env_file=None, database_url=runtime_url, api_hmac_secret=SECRET, cron_secret="cron-secret")


@pytest.fixture
def api(db, settings):
    app = create_app(settings)
    with TestClient(app):  # runs startup and shutdown so the pool opens and closes
        yield SignedClient(app)
