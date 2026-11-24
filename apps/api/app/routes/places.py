from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field, ValidationError, model_validator

from app.db import Cur
from app.models import Near, ProvinceCode, Strict
from app.search import repository as repo
from app.search.tags import LABELS, TAGS

router = APIRouter(prefix="/v1")
Degrees = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


def _floats(raw: str, count: int) -> list[float]:
    try:
        values = [float(x) for x in raw.split(",")]
    except ValueError:
        values = []
    if len(values) != count:
        raise HTTPException(422, "bad_coordinates")
    return values


def _near(raw: str) -> Near:
    lat, lon, radius = _floats(raw, 3)
    try:
        return Near(lat=lat, lon=lon, radius_m=radius)
    except ValidationError as e:
        raise HTTPException(422, "bad_coordinates") from e


def _bbox(raw: str) -> tuple[float, float, float, float]:
    w, s, e, n = _floats(raw, 4)
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):  # also rejects NaN
        raise HTTPException(422, "bad_coordinates")
    return w, s, e, n


@router.get("/places")
def places(cur: Cur, q: Annotated[str | None, Query(max_length=100)] = None, province: ProvinceCode | None = None,
           tag: Annotated[list[str] | None, Query(max_length=15)] = None, bbox: str | None = None, near: str | None = None,
           demo: bool = False, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> dict:
    if set(tag or []) - set(TAGS):
        raise HTTPException(422, "unknown_tag")
    return {"places": repo.list_places(cur, name=q, province=province, tags=tag, bbox=_bbox(bbox) if bbox else None,
                                       near=_near(near) if near else None, demo=demo, limit=limit)}


class AreaSearch(Strict):
    near: Near | None = None
    bbox: tuple[Degrees, Degrees, Degrees, Degrees] | None = None
    q: Annotated[str, Field(max_length=100)] | None = None
    tags: list[str] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def one_valid_area(self):
        if (self.near is None) == (self.bbox is None):
            raise ValueError("give near or bbox")
        if self.bbox is not None:
            w, s, e, n = self.bbox
            if not (w < e <= 180 and -90 <= s < n <= 90):
                raise ValueError("bad bbox")
        return self


@router.post("/search")
def area_search(cur: Cur, body: AreaSearch) -> dict:
    """POST so a visitor's coordinates never appear in URL logs."""
    if set(body.tags) - set(TAGS):
        raise HTTPException(422, "unknown_tag")
    return {"places": repo.list_places(cur, name=body.q, tags=body.tags, near=body.near, bbox=body.bbox, limit=100)}


@router.get("/places/{slug}")
def place(cur: Cur, slug: str):
    found = repo.get_place(cur, slug)
    if found is None:
        raise HTTPException(404, "not_found")
    return found


@router.get("/places/{slug}/nearby")
def nearby(cur: Cur, slug: str) -> dict:
    found = repo.get_place(cur, slug)
    if found is None:
        raise HTTPException(404, "not_found")
    return {"places": repo.nearby(cur, found)}


@router.get("/meta")
def meta(cur: Cur) -> dict:
    return {**repo.meta(cur), "tags": [{"tag": t, "label": LABELS[t]} for t in TAGS]}
