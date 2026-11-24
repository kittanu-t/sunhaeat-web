import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.main import create_app
from app.models import Filters, Near
from app.search.repository import search
from app.settings import Settings
from testsupport.api import SECRET, SignedClient, add_place


def run(db, **filters):
    with db.conn.cursor(row_factory=dict_row) as cur:
        return search(cur, Filters(**filters))


@pytest.fixture
def catalog(db):
    add_place(db, "ร้าน ส้ม ตำ ระเบิด", tags=["isan"], slug="tam")
    add_place(db, "ลาบนัว", tags=["isan"], lat=16.60, slug="lab", confidence=0.95)
    add_place(db, "กาแฟดี", tags=["coffee"], province="TH-30", lat=14.97, lon=102.1, slug="cafe")
    add_place(db, "ครัวสมมติถูก", tags=["isan"], price=(40, 90), demo=True, slug="demo-cheap", description="x")
    add_place(db, "ครัวสมมติแพง", tags=["isan"], price=(40, 300), demo=True, slug="demo-dear", description="x")


def test_unknown_price_goes_to_maybe(db, catalog):
    r = run(db, tags=["isan"], budget_per_person=100)
    assert r.matched == [] and {p.slug for p in r.maybe} == {"tam", "lab"} and all(p.price_max is None for p in r.maybe)
    assert [p.slug for p in r.demo] == ["demo-cheap"]


def test_known_price_is_filtered_and_matched(db, catalog):
    add_place(db, "ราคารู้", tags=["isan"], price=(30, 80), slug="known")
    add_place(db, "แพงรู้", tags=["isan"], price=(30, 180), slug="dear")
    r = run(db, tags=["isan"], budget_per_person=100)
    assert [p.slug for p in r.matched] == ["known"] and "dear" not in {p.slug for p in r.maybe}


def test_demo_never_in_real_results(db, catalog):
    r = run(db)
    assert r.matched and not any(p.is_demo for p in r.matched + r.maybe) and r.demo == []


def test_near_orders_by_distance_and_respects_radius(db, catalog):
    r = run(db, near=Near(lat=16.43, lon=102.83, radius_m=30000))
    assert [p.slug for p in r.matched] == ["tam", "lab"]
    assert r.matched[0].distance_m < 1 and 18000 < r.matched[1].distance_m < 20000
    assert [p.slug for p in run(db, near=Near(lat=16.43, lon=102.83, radius_m=1000)).matched] == ["tam"]


@pytest.mark.parametrize("q", ["ร้าน ส้ม ตำ ระเบิด", "ร้านส้มตำระเบิด", "ส้มตําระเบิด", "สมตำระเบิด"])
def test_thai_spelling_variants_find_same_place(api, catalog, q):
    assert api.places(q=q)[0]["name"] == "ร้าน ส้ม ตำ ระเบิด"


@pytest.mark.parametrize("q", ["' or 1=1--", "%", "_", "\\", "%%%"])
def test_search_text_is_literal(api, catalog, q):
    assert api.places(q=q) == []


def test_list_filters(api, catalog):
    assert {p["slug"] for p in api.places(province="TH-30")} == {"cafe"}
    assert {p["slug"] for p in api.places(tag="isan")} == {"tam", "lab"}
    assert {p["slug"] for p in api.places(bbox="102.8,16.4,102.9,16.5")} == {"tam"}
    assert {p["slug"] for p in api.places(near="16.43,102.83,1000")} == {"tam"}
    assert {p["slug"] for p in api.places(demo="true")} == {"demo-cheap", "demo-dear"}
    assert len(api.places(limit=1)) == 1


@pytest.mark.parametrize("params", [
    {"limit": 101}, {"limit": 0}, {"bbox": "1,2,3"}, {"bbox": "a,b,c,d"}, {"bbox": "103,16,102,17"}, {"bbox": "nan,1,2,3"},
    {"near": "16,102,50001"}, {"near": "91,102,10"}, {"near": "16,inf,10"}, {"tag": "nope"}, {"province": "TH-1"}, {"q": "ก" * 101},
])
def test_bad_parameters_are_422(api, catalog, params):
    assert api.get("/v1/places", **params).status_code == 422


def test_detail_has_sources_and_unknowns_are_null(api, catalog):
    p = api.get("/v1/places/tam").json()
    assert p["price_max"] is None and p["menu"] == [] and p["hours"] == []
    assert p["sources"] == [{"dataset": "meta", "license": "CDLA-Permissive-2.0"}]
    assert "phone" not in p and "confidence" not in p


def test_detail_of_demo_has_menu_and_hours(api, db, catalog):
    pid = db.scalar("select id from app.restaurants where slug = 'demo-cheap'")
    db.execute("insert into app.menu_items values (%s, 0, 'ตำไทย', 40)", [pid])
    db.execute("insert into app.opening_hours values (%s, 1, '10:00', '20:00')", [pid])
    p = api.get("/v1/places/demo-cheap").json()
    assert p["menu"] == [{"name": "ตำไทย", "price_thb": 40}]
    assert p["hours"] == [{"weekday": 1, "opens": "10:00", "closes": "20:00"}]


def test_thai_slug_works_in_path(api, db):
    add_place(db, "ตำ", slug="ร้าน-ตำ-1234abcd")
    assert api.get("/v1/places/%E0%B8%A3%E0%B9%89%E0%B8%B2%E0%B8%99-%E0%B8%95%E0%B8%B3-1234abcd").json()["name"] == "ตำ"


def test_unknown_place_is_404(api, catalog):
    assert api.get("/v1/places/none").status_code == 404 and api.get("/v1/places/none/nearby").status_code == 404


def test_nearby_excludes_itself_and_demo(api, catalog):
    places = api.get("/v1/places/tam/nearby").json()["places"]
    assert "tam" not in {p["slug"] for p in places} and not any(p["is_demo"] for p in places)


def test_meta(api, catalog):
    m = api.get("/v1/meta").json()
    assert m["total"] == 3 and {p["code"]: p["count"] for p in m["provinces"]}["TH-40"] == 2
    assert {"tag": "isan", "label": "อีสาน/ส้มตำ"} in m["tags"] and m["release"] == "test"


def test_database_down_is_503_not_500():
    app = create_app(Settings(_env_file=None, database_url="postgresql://x:y@127.0.0.1:1/z", api_hmac_secret=SECRET))
    with TestClient(app):
        r = SignedClient(app).get("/v1/places")
    assert r.status_code == 503 and r.json() == {"detail": "database_unavailable"}


@pytest.mark.parametrize("where", [
    "ST_DWithin(location, ST_SetSRID(ST_MakePoint(102.83, 16.43), 4326)::geography, 1000)",
    "location && ST_MakeEnvelope(102.8, 16.4, 102.9, 16.5, 4326)::geography",
])
def test_spatial_queries_can_use_the_index(db, catalog, where):
    db.execute("set enable_seqscan = off")
    plan = "\n".join(r[0] for r in db.execute(f"explain select 1 from app.restaurants where {where}"))
    assert "restaurants_location" in plan
