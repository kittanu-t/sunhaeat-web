import { readJson, respond } from "@/lib/api";
import { SessionRequest } from "@/lib/contracts";
import { issueSession, SESSION_COOKIE, SESSION_SECONDS } from "@/lib/session";
import { verifyTurnstile } from "@/lib/turnstile";

export function POST(request: Request): Promise<Response> {
  return respond(async () => {
    const { token } = await readJson(request, SessionRequest);
    await verifyTurnstile(token);
    const cookie = `${SESSION_COOKIE}=${issueSession()}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Lax`;
    return new Response(null, { status: 204, headers: { "set-cookie": cookie, "cache-control": "no-store" } });
  });
}
