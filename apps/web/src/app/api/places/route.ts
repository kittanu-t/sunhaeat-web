import { callApi, callerOf, respond } from "@/lib/api";
import { PlaceList } from "@/lib/contracts";

const PARAMS = new Set(["q", "province", "tag", "bbox", "demo", "limit"]);

export function GET(request: Request): Promise<Response> {
  return respond(async () => {
    const query = new URLSearchParams([...new URL(request.url).searchParams].filter(([name]) => PARAMS.has(name)));
    return callApi(PlaceList, `/v1/places${query.size ? `?${query}` : ""}`, callerOf(request.headers));
  });
}
