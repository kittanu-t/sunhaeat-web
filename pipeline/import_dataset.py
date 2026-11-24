"""Load the built dataset and the fictional demo restaurants into Postgres, in one transaction.

From the repository root, with PYTHONPATH="apps/api;." and IMPORT_DATABASE_URL set to an owner connection:
    python -m pipeline.import_dataset data/build
"""
import hashlib
import json
import os
import pathlib
import sys
import uuid

import psycopg

from app.search.normalize import normalize_name

DEMO_PATH = pathlib.Path(__file__).parents[1] / "apps/web/data/demo.json"
COLUMNS = ("id", "slug", "name", "name_normalized", "province_code", "address", "locality", "tags", "description", "website",
           "facebook_url", "price_min", "price_max", "confidence", "is_demo", "dataset_release")


def import_rows(conn: psycopg.Connection, rows: list[dict], demo: list[dict], provinces: dict[str, str], release: str) -> None:
    if not rows:
        raise ValueError("refusing to import an empty dataset")
    demo = [d | {"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "sunhaeat-demo:" + d["slug"]))} for d in demo]
    everything = [r | {"is_demo": False, "dataset_release": release, "description": None} for r in rows]
    everything += [d | {"is_demo": True, "dataset_release": "demo", "name_normalized": normalize_name(d["name"]),
                        "locality": None, "website": None, "facebook_url": None, "confidence": None} for d in demo]
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany("""insert into app.provinces (code, name_th) values (%s, %s)
            on conflict (code) do update set name_th = excluded.name_th""", sorted(provinces.items()))
        cur.execute("create temp table staged (like app.restaurants) on commit drop")
        with cur.copy(f"copy staged ({', '.join(COLUMNS)}, location) from stdin") as copy:  # noqa: S608
            for r in everything:
                copy.write_row([*(r[c] for c in COLUMNS), f"SRID=4326;POINT({r['lon']} {r['lat']})"])
        cur.execute("delete from app.restaurants r where not exists (select 1 from staged s where s.id = r.id)")
        updates = ", ".join(f"{c} = excluded.{c}" for c in (*COLUMNS[1:], "location"))
        cur.execute(f"""insert into app.restaurants ({', '.join(COLUMNS)}, location)
            select {', '.join(COLUMNS)}, location from staged on conflict (id) do update set {updates}""")  # noqa: S608
        for table in ("restaurant_sources", "menu_items", "opening_hours"):
            cur.execute(f"delete from app.{table}")  # noqa: S608
        with cur.copy("copy app.restaurant_sources (restaurant_id, dataset, record_id, license) from stdin") as copy:
            for r in rows:
                for source in r["sources"]:
                    copy.write_row([r["id"], *source])
        cur.executemany("insert into app.menu_items (restaurant_id, position, name, price_thb) values (%s, %s, %s, %s)",
                        [(d["id"], i, m["name"], m["price_thb"]) for d in demo for i, m in enumerate(d["menu"])])
        cur.executemany("insert into app.opening_hours (restaurant_id, weekday, opens, closes) values (%s, %s, %s, %s)",
                        [(d["id"], h["weekday"], h["opens"], h["closes"]) for d in demo for h in d["hours"]])


def main(build: str) -> None:
    folder = pathlib.Path(build)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf8"))
    body = (folder / "restaurants.ndjson").read_bytes()
    if hashlib.sha256(body).hexdigest() != manifest["sha256"]:
        raise SystemExit("restaurants.ndjson does not match manifest.json; rebuild the dataset")
    rows = [json.loads(line) for line in body.decode("utf8").splitlines()]
    demo = json.loads(DEMO_PATH.read_text(encoding="utf8"))
    with psycopg.connect(os.environ["IMPORT_DATABASE_URL"], autocommit=True) as conn:
        import_rows(conn, rows, demo, manifest["provinces"], manifest["release"])
        print("imported", len(rows), "restaurants and", len(demo), "demo restaurants")


if __name__ == "__main__":
    main(sys.argv[1])
