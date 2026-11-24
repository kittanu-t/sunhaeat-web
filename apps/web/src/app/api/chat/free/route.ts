import { callApi, readJson, requireSession, respond } from "@/lib/api";
import { ChatReply, FreeRequest } from "@/lib/contracts";

export const maxDuration = 30;

export function POST(request: Request): Promise<Response> {
  return respond(async () => {
    const caller = requireSession(request);
    const body = await readJson(request, FreeRequest);
    return callApi(ChatReply, "/v1/chat/free", caller, { method: "POST", body, timeoutMs: 25_000 });
  });
}
