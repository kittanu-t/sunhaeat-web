import { ApiError } from "@/lib/api";

/** Throws unless Cloudflare confirms the token. The visitor's address is not sent. */
export async function verifyTurnstile(token: string): Promise<void> {
  const secret = process.env.TURNSTILE_SECRET_KEY;
  const isTestKey = secret?.startsWith("1x0000");
  if (!secret || (isTestKey && process.env.VERCEL_ENV === "production")) throw new ApiError(503, "not_configured");
  let ok: boolean;
  try {
    const response = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
      method: "POST", body: new URLSearchParams({ secret, response: token }), cache: "no-store", signal: AbortSignal.timeout(5000),
    });
    ok = response.ok && (await response.json()).success === true;
  } catch {
    throw new ApiError(503, "unavailable");
  }
  if (!ok) throw new ApiError(403, "verification_failed");
}
