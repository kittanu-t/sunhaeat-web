import { callApi, readJson, requireSession, respond } from "@/lib/api";
import { GuidedRequest, GuidedResponse } from "@/lib/contracts";

export function POST(request: Request): Promise<Response> {
  return respond(async () => {
    const caller = requireSession(request);
    const body = await readJson(request, GuidedRequest);
    return callApi(GuidedResponse, "/v1/chat/guided", caller, { method: "POST", body });
  });
}
