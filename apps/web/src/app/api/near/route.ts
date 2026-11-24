import { callApi, callerOf, readJson, respond } from "@/lib/api";
import { NearRequest, PlaceList } from "@/lib/contracts";

const round = (degrees: number) => Math.round(degrees * 1000) / 1000; // about 110 m

/** POST so neither a visitor's position nor the area they look at appears in URL logs. */
export function POST(request: Request): Promise<Response> {
  return respond(async () => {
    const wanted = await readJson(request, NearRequest);
    let body: object = wanted;
    if ("lat" in wanted) {
      const { lat, lon, ...rest } = wanted;
      body = { near: { lat: round(lat), lon: round(lon), radius_m: 5000 }, ...rest };
    }
    return callApi(PlaceList, "/v1/search", callerOf(request.headers), { method: "POST", body });
  });
}
