from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.search.tags import TAGS

ProvinceCode = Annotated[str, Field(pattern=r"^TH-(3[0-9]|4[0-9])$")]
Term = Annotated[str, Field(min_length=1, max_length=60)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Near(Strict):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    radius_m: int = Field(default=5000, ge=100, le=50_000)


class Filters(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    province_code: ProvinceCode | None = None
    tags: list[str] = Field(default_factory=list, max_length=15)
    terms: list[Term] = Field(default_factory=list, max_length=5)
    near: Near | None = None
    budget_per_person: int | None = Field(default=None, ge=1, le=100_000)
    needs_clarification: bool = False

    @field_validator("tags")
    @classmethod
    def known_tags(cls, tags: list[str]) -> list[str]:
        if unknown := set(tags) - set(TAGS):
            raise ValueError(f"unknown tags: {sorted(unknown)}")
        return tags


class Place(BaseModel):
    id: UUID
    slug: str
    name: str
    province_code: str
    province_name: str
    lat: float
    lon: float
    address: str | None
    locality: str | None
    tags: list[str]
    website: str | None
    facebook_url: str | None
    price_min: int | None
    price_max: int | None
    is_demo: bool
    distance_m: float | None = None


class MenuItem(BaseModel):
    name: str
    price_thb: int | None


class Hours(BaseModel):
    weekday: int
    opens: str
    closes: str


class Source(BaseModel):
    dataset: str
    license: str


class PlaceDetail(Place):
    description: str | None
    menu: list[MenuItem]
    hours: list[Hours]
    sources: list[Source]
    dataset_release: str


class SearchResult(BaseModel):
    matched: list[Place] = Field(default_factory=list)
    maybe: list[Place] = Field(default_factory=list)
    demo: list[Place] = Field(default_factory=list)
