import { callApi, callerOf, respond, slugPath } from "@/lib/api";
import { PlaceList } from "@/lib/contracts";

export function GET(request: Request, { params }: { params: Promise<{ slug: string }> }): Promise<Response> {
  return respond(async () => callApi(PlaceList, `/v1/places/${slugPath((await params).slug)}/nearby`, callerOf(request.headers)));
}
