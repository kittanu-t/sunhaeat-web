import { callApi, callerOf, respond } from "@/lib/api";
import { Meta } from "@/lib/contracts";

export function GET(request: Request): Promise<Response> {
  return respond(async () => callApi(Meta, "/v1/meta", callerOf(request.headers)), "public, max-age=300");
}
