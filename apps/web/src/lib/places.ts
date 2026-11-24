import { headers } from "next/headers";
import { cache } from "react";
import demoData from "../../data/demo.json";
import { ApiError, callApi, callerOf, slugPath } from "@/lib/api";
import { Meta, PlaceDetail, PlaceList, type Place } from "@/lib/contracts";
import { PROVINCES } from "@/lib/labels";

const caller = async () => callerOf(await headers());

/** The fictional places bundled with the site, so their pages open even when the database is paused. */
export const DEMO_PLACES: PlaceDetail[] = demoData.map((d, i) => ({
  id: `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`,
  slug: d.slug, name: d.name, province_code: d.province_code, province_name: PROVINCES[d.province_code],
  lat: d.lat, lon: d.lon, address: d.address, locality: null, tags: d.tags, website: null, facebook_url: null,
  price_min: d.price_min, price_max: d.price_max, is_demo: true, distance_m: null, description: d.description,
  menu: d.menu, hours: d.hours, sources: [], dataset_release: "demo",
}));

/** null when the API or its database cannot answer. */
async function orNull<T>(work: () => Promise<T>): Promise<T | null> {
  try {
    return await work();
  } catch (error) {
    if (error instanceof ApiError && error.status >= 500) return null;
    throw error;
  }
}

export const getMeta = cache(() => orNull(async () => callApi(Meta, "/v1/meta", await caller())));

export async function findPlaces(query: URLSearchParams): Promise<Place[] | null> {
  const list = await orNull(async () => callApi(PlaceList, `/v1/places?${query}`, await caller()));
  return list && list.places;
}

/** undefined: no such place; null: cannot say right now. */
export const getPlace = cache(async (slug: string): Promise<PlaceDetail | null | undefined> => {
  let path: string;
  try {
    path = slugPath(slug);
    return (await orNull(async () => callApi(PlaceDetail, `/v1/places/${path}`, await caller()))) ?? DEMO_PLACES.find((p) => p.slug === slug) ?? null;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return undefined;
    throw error;
  }
});

export async function getNearby(slug: string): Promise<Place[]> {
  const list = await orNull(async () => callApi(PlaceList, `/v1/places/${slugPath(slug)}/nearby`, await caller()));
  return list?.places ?? [];
}
