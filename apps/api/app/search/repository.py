"""Read-only catalog queries. Every user value is a bound parameter."""
from psycopg import Cursor

from app.models import Filters, Near, Place, PlaceDetail, SearchResult
from app.search.normalize import normalize_name

_COLUMNS = """r.id, r.slug, r.name, r.province_code, p.name_th as province_name,
  ST_Y(r.location::geometry) as lat, ST_X(r.location::geometry) as lon, r.address, r.locality, r.tags,
  r.website, r.facebook_url, r.price_min, r.price_max, r.is_demo"""
_FROM = "from app.restaurants r join app.provinces p on p.code = r.province_code"
_POINT = "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326)::geography"
DEMO_LIMIT = 3


def _literal(text: str) -> str:
    """A LIKE pattern matching the normalized text literally."""
    escaped = normalize_name(text).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_places(cur: Cursor, *, name: str | None = None, terms: list[str] | None = None, province: str | None = None,
                tags: list[str] | None = None, bbox: tuple[float, float, float, float] | None = None, near: Near | None = None,
                demo: bool = False, limit: int = 20) -> list[Place]:
    where, params = ["r.is_demo = %(demo)s"], {"demo": demo, "limit": limit}
    order = ["r.confidence desc nulls last", "r.id"]
    columns = _COLUMNS
    if province:
        where.append("r.province_code = %(province)s")
        params["province"] = province
    if tags:
        where.append("r.tags && %(tags)s::text[]")
        params["tags"] = tags
    for i, term in enumerate(terms or []):
        where.append(f"r.name_normalized like %(term{i})s")
        params[f"term{i}"] = _literal(term)
    if bbox:
        where.append("r.location && ST_MakeEnvelope(%(w)s, %(s)s, %(e)s, %(n)s, 4326)::geography")
        params |= dict(zip("wsen", bbox, strict=True))
    if near:
        where.append(f"ST_DWithin(r.location, {_POINT}, %(radius)s)")
        columns += f", ST_Distance(r.location, {_POINT}) as distance_m"
        order.insert(0, "distance_m")
        params |= {"lat": near.lat, "lon": near.lon, "radius": near.radius_m}

    def run(extra: list[str], ranking: list[str]) -> list[Place]:
        sql = f"select {columns} {_FROM} where {' and '.join(where + extra)} order by {', '.join(ranking)} limit %(limit)s"  # noqa: S608
        return [Place(**row) for row in cur.execute(sql, params).fetchall()]

    if not name or not normalize_name(name):
        return run([], order)
    params |= {"name": normalize_name(name), "pattern": _literal(name)}
    found = run(["r.name_normalized like %(pattern)s"], ["(r.name_normalized = %(name)s) desc", *order])
    return found or run(["similarity(r.name_normalized, %(name)s) >= 0.3"],
                        ["similarity(r.name_normalized, %(name)s) desc", *order])


def search(cur: Cursor, f: Filters, limit: int = 20) -> SearchResult:
    """Real places split by whether the budget is confirmed; fictional ones only in their own lane."""
    budget = f.budget_per_person
    # Over-fetch so that known-price places filtered out below do not empty the list.
    rows = list_places(cur, name=f.name, terms=f.terms, province=f.province_code, tags=f.tags, near=f.near,
                       limit=limit if budget is None else 200)
    if budget is None:
        return SearchResult(matched=rows)
    demo = [p for p in list_places(cur, tags=f.tags, demo=True, limit=100) if p.price_max is not None and p.price_max <= budget]
    demo.sort(key=lambda p: (p.province_code != f.province_code, p.slug))
    return SearchResult(
        matched=[p for p in rows if p.price_max is not None and p.price_max <= budget][:limit],
        maybe=[p for p in rows if p.price_max is None][:limit],
        demo=demo[:DEMO_LIMIT],
    )


def get_place(cur: Cursor, slug: str) -> PlaceDetail | None:
    row = cur.execute(f"select {_COLUMNS}, r.description, r.dataset_release {_FROM} where r.slug = %s", [slug]).fetchone()  # noqa: S608
    if row is None:
        return None
    menu = cur.execute("select name, price_thb from app.menu_items where restaurant_id = %s order by position", [row["id"]]).fetchall()
    hours = cur.execute("""select weekday, to_char(opens, 'HH24:MI') as opens, to_char(closes, 'HH24:MI') as closes
        from app.opening_hours where restaurant_id = %s order by weekday""", [row["id"]]).fetchall()
    sources = cur.execute("""select distinct dataset, license from app.restaurant_sources
        where restaurant_id = %s order by dataset""", [row["id"]]).fetchall()
    return PlaceDetail(**row, menu=menu, hours=hours, sources=sources)


def nearby(cur: Cursor, place: Place, limit: int = 6) -> list[Place]:
    near = Near(lat=place.lat, lon=place.lon, radius_m=3000)
    return [p for p in list_places(cur, near=near, limit=limit + 1) if p.id != place.id][:limit]


def meta(cur: Cursor) -> dict:
    provinces = cur.execute("""select p.code, p.name_th as name, count(r.id) filter (where not r.is_demo) as count
        from app.provinces p left join app.restaurants r on r.province_code = p.code group by p.code order by p.code""").fetchall()
    release = cur.execute("select max(dataset_release) as release from app.restaurants where not is_demo").fetchone()
    return {"provinces": provinces, "total": sum(p["count"] for p in provinces), **release}
