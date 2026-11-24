import json
import pathlib

import pytest

from pipeline.build_dataset import finalize
from pipeline.import_dataset import import_rows
from pipeline.tests.test_build import row

DEMO = json.loads((pathlib.Path(__file__).parents[2] / "apps/web/data/demo.json").read_text(encoding="utf8"))
PROVINCES = {f"TH-{n}": f"จังหวัด {n}" for n in range(30, 50)}
ROWS = finalize([row(source_id=s, lat=16 + i) for i, s in enumerate("abc")])


def dump(db):
    tables = ("provinces", "restaurants", "restaurant_sources", "menu_items", "opening_hours")
    return {t: sorted(map(str, db.execute(f"select * from app.{t}").fetchall())) for t in tables}


def counts(db):
    return [db.scalar(f"select count(*) from app.restaurants where is_demo = {x}") for x in ("false", "true")]


def run(db, rows=ROWS, demo=DEMO):
    import_rows(db.conn, rows, demo, PROVINCES, "test-release")


def test_import_twice_is_identical(db):
    run(db)
    first = dump(db)
    run(db)
    assert dump(db) == first and counts(db) == [3, 12]


def test_rows_missing_from_release_go_but_demo_stays(db):
    run(db)
    run(db, ROWS[1:])
    assert counts(db) == [2, 12]


def test_changed_row_is_updated_in_place(db):
    run(db)
    run(db, [ROWS[0] | {"name": "ชื่อใหม่", "name_normalized": "ชื่อใหม่"}, *ROWS[1:]])
    assert db.scalar("select name from app.restaurants where id=%s", [ROWS[0]["id"]]) == "ชื่อใหม่"


def test_failed_import_leaves_previous_data(db):
    run(db)
    before = dump(db)
    with pytest.raises(Exception, match="restaurants_price"):
        run(db, [ROWS[0] | {"price_min": -1}])
    assert dump(db) == before


def test_empty_dataset_is_refused(db):
    with pytest.raises(ValueError, match="empty"):
        run(db, [])


def test_location_axis_order(db):
    run(db)
    lon = db.scalar("select ST_X(location::geometry) from app.restaurants where id=%s", [ROWS[0]["id"]])
    assert round(lon, 2) == 102.83


def test_demo_restaurants_are_complete():
    assert len(DEMO) == len({d["slug"] for d in DEMO}) == 12
    for d in DEMO:
        prices = [m["price_thb"] for m in d["menu"]]
        assert d["slug"].startswith("demo-") and d["hours"] and d["description"] and "phone" not in d
        assert (d["price_min"], d["price_max"]) == (min(prices), max(prices))
        assert 14 < d["lat"] < 18.6 and 100.7 < d["lon"] < 105.8
