"""Turn the raw Overture extract into the dataset the site imports.

From the repository root, with PYTHONPATH="apps/api;.":
    python -m pipeline.build_dataset data/raw data/build
"""
import hashlib
import json
import math
import pathlib
import re
import sys
import uuid
from collections import defaultdict
from urllib.parse import urlsplit

import duckdb

from app.search.normalize import normalize_name
from pipeline.fetch_overture import RELEASE
from pipeline.spike_gate import CATEGORIES, FOOD, NON_FOOD, SIMPLIFY_DEGREES
from pipeline.tagging import clean_text, slug_for, tags_for

MIN_CONFIDENCE = 0.8
MERGE_RADIUS_M = 150
_FACEBOOK = re.compile(r"https://www\.facebook\.com/[A-Za-z0-9.\-]+/?")


def extract(raw: pathlib.Path) -> tuple[list[dict], dict[str, str]]:
    """Rows passing the data-gate rules, and province code -> Thai name."""
    c = duckdb.connect()
    c.execute("install spatial; load spatial")
    # DuckDB takes the file list as a parameter, so a non-ASCII path needs no quoting.
    c.execute("create table raw_province as select * from read_parquet(?)", [str(raw / "provinces.parquet")])
    c.execute("create table raw_place as select * from read_parquet(?)", [str(raw / "places.parquet")])
    c.execute("""create table province as select region as code, names.primary as name, bbox,
        ST_MakeValid(ST_Simplify(geometry, ?)) as g from raw_province
        where class = 'land' and try_cast(replace(region, 'TH-', '') as int) between 30 and 49""", [SIMPLIFY_DEGREES])
    cur = c.execute("""select f.id as source_id, f.names.primary as name, f.taxonomy.primary as taxonomy,
          p.code as province_code, ST_Y(f.geometry) as lat, ST_X(f.geometry) as lon,
          f.addresses[1].freeform as address, f.addresses[1].locality as locality, f.websites, f.socials, f.confidence,
          list_transform(f.sources, lambda s: {'dataset': s.dataset, 'record_id': s.record_id, 'license': s.license}) as sources
        from raw_place f join province p
          on ST_X(f.geometry) between p.bbox.xmin and p.bbox.xmax and ST_Y(f.geometry) between p.bbox.ymin and p.bbox.ymax
         and ST_Contains(p.g, f.geometry)
        where f.taxonomy.hierarchy[1] = 'food_and_drink' and list_contains(?, f.basic_category)
          and f.names.primary is not null and f.confidence >= ?
          and coalesce(f.operating_status, 'open') = 'open'
          and not (regexp_matches(f.names.primary, ?) and not regexp_matches(f.names.primary, ?))""",
        [list(CATEGORIES), MIN_CONFIDENCE, f"(?i){NON_FOOD}", f"(?i){FOOD}"])
    columns = [d[0] for d in cur.description]
    rows = [dict(zip(columns, r, strict=True)) for r in cur.fetchall()]
    provinces = {code: name.removeprefix("จังหวัด") for code, name in c.execute("select code, name from province").fetchall()}
    return rows, provinces


def _metres(a: dict, b: dict) -> float:
    dy = (a["lat"] - b["lat"]) * 111_320
    dx = (a["lon"] - b["lon"]) * 111_320 * math.cos(math.radians(a["lat"]))
    return math.hypot(dx, dy)


def _website(urls: list[str] | None) -> str | None:
    for url in urls or []:
        try:
            parts = urlsplit(url)
        except ValueError:
            continue
        if (parts.scheme == "https" and parts.hostname and "." in parts.hostname and parts.username is None
                and len(url) <= 500 and not re.search(r"[\s<>\"']", url)):
            return url
    return None


def _record(row: dict, name: str) -> dict:
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "overture:" + row["source_id"])),
        "source_id": row["source_id"],
        "slug": slug_for(name, row["source_id"]),
        "name": name,
        "name_normalized": normalize_name(name),
        "province_code": row["province_code"],
        "lat": round(row["lat"], 6),
        "lon": round(row["lon"], 6),
        "address": clean_text(row["address"] or "") or None,
        "locality": clean_text(row["locality"] or "") or None,
        "tags": tags_for(name, row["taxonomy"] or ""),
        "website": _website(row["websites"]),
        "facebook_url": next((u for u in row["socials"] or [] if _FACEBOOK.fullmatch(u)), None),
        "price_min": None,
        "price_max": None,
        "confidence": round(row["confidence"], 4),
        "sources": sorted({
            (s["dataset"], s["record_id"] or row["source_id"], s["license"] or "unknown") for s in row["sources"]}),
    }


def finalize(rows: list[dict]) -> list[dict]:
    """Clean, keep one row per source and merge same-name places within MERGE_RADIUS_M."""
    by_source: dict[str, dict] = {}
    for row in sorted(rows, key=lambda r: (r["source_id"], r["province_code"])):
        by_source.setdefault(row["source_id"], row)
    kept: dict[str, list[dict]] = defaultdict(list)
    for row in sorted(by_source.values(), key=lambda r: (-r["confidence"], r["source_id"])):
        name = clean_text(row["name"])[:200]
        if len(normalize_name(name)) < 2:
            continue
        group = kept[normalize_name(name)]
        if all(_metres(row, other) > MERGE_RADIUS_M for other in group):
            group.append(_record(row, name))
    return sorted((r for group in kept.values() for r in group), key=lambda r: r["id"])


def main(raw: str, out: str) -> None:
    sys.stdout.reconfigure(encoding="utf8")
    rows, provinces = extract(pathlib.Path(raw))
    records = finalize(rows)
    if len({r["slug"] for r in records}) != len(records):
        raise SystemExit("slug collision")
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records).encode()
    per_province = {code: sum(r["province_code"] == code for r in records) for code in sorted(provinces)}
    tags = {t: sum(t in r["tags"] for r in records) for t in sorted({t for r in records for t in r["tags"]})}
    manifest = {
        "release": RELEASE, "extracted": len(rows), "total": len(records), "sha256": hashlib.sha256(body).hexdigest(),
        "provinces": provinces, "per_province": per_province, "tags": tags,
        "untagged": sum(not r["tags"] for r in records),
        "without_source_license": sum(any(s[2] == "unknown" for s in r["sources"]) or not r["sources"] for r in records),
    }
    target = pathlib.Path(out)
    target.mkdir(parents=True, exist_ok=True)
    (target / "restaurants.ndjson").write_bytes(body)
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
