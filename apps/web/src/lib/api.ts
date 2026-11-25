import { createHash, createHmac } from "node:crypto";
import type { z } from "zod";
import { ipHash, sessionFrom } from "@/lib/session";

const MAX_BODY_BYTES = 16_384;

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string) {
    super(code);
  }
}

/**
 * Percent-decoded path plus the query's decoded pairs, escaped one way. Hosts rewrite the raw query in transit
 * ("+" becomes "%20", "%7E" becomes "~"), so it cannot be signed as sent.
 */
export function signedTarget(path: string): string {
  const [pathname, query] = path.split("?", 2);
  const encoded = [...new URLSearchParams(query)].map((pair) => pair.map(encodeURIComponent).join("=")).join("&");
  return decodeURIComponent(pathname) + (encoded && `?${encoded}`);
}

/** target comes from signedTarget. */
export function sign(secret: string, ts: string, method: string, target: string, session: string, ip: string, body: string): string {
  const digest = createHash("sha256").update(body).digest("hex");
  return createHmac("sha256", secret).update([ts, method, target, session, ip, digest].join("\n")).digest("hex");
}

interface Caller { session: string; ip: string }
interface Call { method?: "GET" | "POST"; body?: unknown; timeoutMs?: number }

export function callerOf(headers: Headers, session = "anonymous"): Caller {
  try {
    return { session, ip: ipHash(headers) };
  } catch {
    throw new ApiError(503, "not_configured");
  }
}

/** Signed call to the Python API; path must already be percent-encoded. */
export async function callApi<T extends z.ZodType>(schema: T, path: string, caller: Caller, call: Call = {}): Promise<z.infer<T>> {
  const { method = "GET", body, timeoutMs = 8000 } = call;
  const base = process.env.API_BASE_URL;
  const secret = process.env.API_HMAC_SECRET;
  if (!base || !secret) throw new ApiError(503, "not_configured");
  const target = signedTarget(path);
  const text = body === undefined ? "" : JSON.stringify(body);
  const ts = String(Math.floor(Date.now() / 1000));
  let response: Response;
  try {
    response = await fetch(base + path, {
      method,
      body: body === undefined ? undefined : text,
      headers: {
        ...(body === undefined ? {} : { "content-type": "application/json" }),
        "x-she-timestamp": ts, "x-she-session": caller.session, "x-she-ip": caller.ip,
        "x-she-signature": sign(secret, ts, method, target, caller.session, caller.ip, text),
      },
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new ApiError(503, "unavailable");
  }
  if (!response.ok) {
    const known: Record<number, [number, string]> = {
      404: [404, "not_found"], 422: [400, "bad_request"], 429: [429, "rate_limited"], 503: [503, "unavailable"],
    };
    throw new ApiError(...(known[response.status] ?? [502, "bad_upstream"] as [number, string]));
  }
  const parsed = schema.safeParse(await response.json().catch(() => undefined));
  if (!parsed.success) throw new ApiError(502, "bad_upstream");
  return parsed.data;
}

/** Run a handler and turn ApiError into a small JSON answer that never repeats upstream text. */
export async function respond(handler: () => Promise<Response | object>, cache = "no-store"): Promise<Response> {
  try {
    const result = await handler();
    return result instanceof Response ? result : Response.json(result, { headers: { "cache-control": cache } });
  } catch (error) {
    const { status, code } = error instanceof ApiError ? error : new ApiError(500, "internal");
    return Response.json({ error: code }, { status, headers: { "cache-control": "no-store" } });
  }
}

/** Same-origin JSON only, bounded, matching the schema. */
export async function readJson<T extends z.ZodType>(request: Request, schema: T): Promise<z.infer<T>> {
  const origin = request.headers.get("origin");
  const site = request.headers.get("sec-fetch-site");
  if (!origin || !URL.canParse(origin) || new URL(origin).host !== request.headers.get("host") || (site && site !== "same-origin"))
    throw new ApiError(403, "forbidden");
  if (request.headers.get("content-type")?.split(";")[0].trim() !== "application/json") throw new ApiError(415, "json_only");
  const reader = request.body?.getReader();
  const chunks: Uint8Array[] = [];
  for (let size = 0; reader; ) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.length;
    if (size > MAX_BODY_BYTES) {
      await reader.cancel();
      throw new ApiError(413, "too_large");
    }
    chunks.push(value);
  }
  let json: unknown;
  try {
    json = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)));
  } catch {
    throw new ApiError(400, "bad_request");
  }
  const parsed = schema.safeParse(json);
  if (!parsed.success) throw new ApiError(400, "bad_request");
  return parsed.data;
}

export function requireSession(request: Request): Caller {
  let session: string | null;
  try {
    session = sessionFrom(request);
  } catch {
    throw new ApiError(503, "not_configured");
  }
  if (!session) throw new ApiError(401, "session_required");
  return callerOf(request.headers, session);
}

/** Path segment for a place, or a 404 when it cannot be one of our slugs. */
export function slugPath(raw: string): string {
  let slug: string;
  try {
    slug = decodeURIComponent(raw);
  } catch {
    throw new ApiError(404, "not_found");
  }
  if (!/^[0-9a-zก-๎-]{1,200}$/.test(slug)) throw new ApiError(404, "not_found");
  return encodeURIComponent(slug);
}
