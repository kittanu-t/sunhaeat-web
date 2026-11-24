import { callApi, callerOf, respond, slugPath } from "@/lib/api";
import { PlaceDetail } from "@/lib/contracts";

export function GET(request: Request, { params }: { params: Promise<{ slug: string }> }): Promise<Response> {
  return respond(async () => callApi(PlaceDetail, `/v1/places/${slugPath((await params).slug)}`, callerOf(request.headers)));
}
