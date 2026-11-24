import { createHash } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import vectors from "../../../../tests/fixtures/hmac.json";
import { POST as chatFree } from "@/app/api/chat/free/route";
import { POST as chatGuided } from "@/app/api/chat/guided/route";
import { GET as getMeta } from "@/app/api/meta/route";
import { POST as postNear } from "@/app/api/near/route";
import { GET as getPlace } from "@/app/api/places/[slug]/route";
import { GET as getPlaces } from "@/app/api/places/route";
import { POST as createSession } from "@/app/api/session/route";
import { sign } from "@/lib/api";
import { ipHash, issueSession, readSession } from "@/lib/session";

const ORIGIN = "https://sunhaeat.test";
const place = {
  id: "0b0e6a3e-6a0e-4a53-9d2c-0c6f1f1a2b3c", slug: "ร้าน-ตำ-1", name: "ตำ", province_code: "TH-40", province_name: "ขอนแก่น",
  lat: 16.4, lon: 102.8, address: null, locality: null, tags: ["isan"], website: null, facebook_url: null, price_min: null,
  price_max: null, is_demo: false, distance_m: null,
};
const filters = { name: null, province_code: "TH-40", tags: ["isan"], terms: [], near: null, budget_per_person: null, needs_clarification: false };
const reply = { mode: "rules", text: "พบ 1 ร้าน", filters, result: { matched: [place], maybe: [], demo: [] }, disclaimer: "d", ai_unavailable: null, ai_code: null };

let upstream: { url: string; init: RequestInit }[];
let answer: () => Response | Promise<Response>;

beforeEach(() => {
  vi.stubEnv("API_BASE_URL", "https://api.test");
  vi.stubEnv("API_HMAC_SECRET", "hmac-secret");
  vi.stubEnv("SESSION_SECRET", "session-secret-session-secret-0123");
  vi.stubEnv("TURNSTILE_SECRET_KEY", "turnstile-secret");
  upstream = [];
  answer = () => Response.json({ places: [place] });
  vi.stubGlobal("fetch", async (url: string | URL, init: RequestInit = {}) => {
    upstream.push({ url: String(url), init });
    return answer();
  });
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function post(path: string, body: unknown, headers: Record<string, string | null> = {}) {
  const all: Record<string, string | null> = {
    host: "sunhaeat.test", origin: ORIGIN, "content-type": "application/json", "x-real-ip": "203.0.113.9", ...headers,
  };
  const sent = Object.fromEntries(Object.entries(all).filter(([, v]) => v !== null)) as Record<string, string>;
  return new Request(ORIGIN + path, { method: "POST", headers: sent, body: typeof body === "string" ? body : JSON.stringify(body) });
}
const withCookie = () => ({ cookie: `she_session=${issueSession()}` });
const header = (name: string) => new Headers(upstream[0].init.headers).get(name);

describe("request signing", () => {
  it.each(vectors)("matches the API vector: $name", (v) => {
    expect(sign(v.secret, v.ts, v.method, v.target, v.session, v.ip, v.body)).toBe(v.signature);
  });

  it("signs the decoded Thai path it calls", async () => {
    answer = () => Response.json({ ...place, description: null, menu: [], hours: [], sources: [], dataset_release: "r" });
    const slug = "ร้าน-ตำ-1";
    const res = await getPlace(new Request(`${ORIGIN}/api/places/${encodeURIComponent(slug)}`), { params: Promise.resolve({ slug }) });
    expect(res.status).toBe(200);
    expect(upstream[0].url).toBe(`https://api.test/v1/places/${encodeURIComponent(slug)}`);
    expect(header("x-she-signature")).toBe(
      sign("hmac-secret", header("x-she-timestamp")!, "GET", `/v1/places/${slug}`, "anonymous", header("x-she-ip")!, ""));
  });

  it("decodes a slug the router left encoded exactly once", async () => {
    answer = () => new Response("{}", { status: 404 });
    const slug = encodeURIComponent("ร้าน");
    await getPlace(new Request(ORIGIN), { params: Promise.resolve({ slug }) });
    expect(upstream[0].url).toBe(`https://api.test/v1/places/${slug}`);
  });

  it.each(["../meta", "a/b", "a?x=1", "%E0%A4%A", "", "x".repeat(201)])("rejects slug %j without calling the API", async (slug) => {
    const res = await getPlace(new Request(ORIGIN), { params: Promise.resolve({ slug }) });
    expect(res.status).toBe(404);
    expect(upstream).toHaveLength(0);
  });
});

describe("places", () => {
  it("forwards only known query parameters", async () => {
    await getPlaces(new Request(`${ORIGIN}/api/places?q=${encodeURIComponent("ตำ")}&tag=isan&tag=noodle&evil=1&limit=5`));
    expect(upstream[0].url).toBe(`https://api.test/v1/places?q=${encodeURIComponent("ตำ")}&tag=isan&tag=noodle&limit=5`);
  });

  it("never forwards coordinates from a URL", async () => {
    await getPlaces(new Request(`${ORIGIN}/api/places?near=16.4,102.8,500`));
    expect(upstream[0].url).toBe("https://api.test/v1/places");
  });

  it("sends a near search by POST with rounded coordinates", async () => {
    const res = await postNear(post("/api/near", { lat: 16.432198, lon: 102.834567, tags: ["isan"] }));
    expect(res.status).toBe(200);
    expect(upstream[0].url).toBe("https://api.test/v1/search");
    expect(JSON.parse(String(upstream[0].init.body))).toEqual({ near: { lat: 16.432, lon: 102.835, radius_m: 5000 }, tags: ["isan"] });
  });

  it.each([[{ lat: 91, lon: 1 }], [{ lat: 1 }], [{ lat: "1", lon: 1 }]])("rejects near search %j", async (body) => {
    expect((await postNear(post("/api/near", body))).status).toBe(400);
    expect((await postNear(post("/api/near", { lat: 1, lon: 1 }, { origin: "https://evil.test" }))).status).toBe(403);
    expect(upstream).toHaveLength(0);
  });

  it("returns 502 when the API answer does not match the contract", async () => {
    answer = () => Response.json({ places: [{ ...place, lat: "16" }] });
    expect((await getPlaces(new Request(`${ORIGIN}/api/places`))).status).toBe(502);
  });

  it("drops fields outside the contract", async () => {
    answer = () => Response.json({ places: [{ ...place, phone: "0812345678" }] });
    expect(await (await getPlaces(new Request(`${ORIGIN}/api/places`))).text()).not.toContain("phone");
  });

  it.each([["javascript:alert(1)"], ["http://a.test"]])("refuses unsafe link %s from the API", async (website) => {
    answer = () => Response.json({ places: [{ ...place, website }] });
    expect((await getPlaces(new Request(`${ORIGIN}/api/places`))).status).toBe(502);
  });

  it.each([[503, 503], [500, 502], [401, 502], [422, 400], [429, 429], [404, 404]])("maps upstream %i to %i", async (from, to) => {
    answer = () => new Response('{"detail":"internal words"}', { status: from });
    const res = await getPlaces(new Request(`${ORIGIN}/api/places`));
    expect(res.status).toBe(to);
    expect(await res.text()).not.toContain("internal words");
  });

  it("is 503 when the API cannot be reached", async () => {
    answer = () => Promise.reject(new Error("ECONNREFUSED"));
    expect((await getMeta(new Request(`${ORIGIN}/api/meta`))).status).toBe(503);
  });

  it.each(["API_HMAC_SECRET", "API_BASE_URL", "SESSION_SECRET"])("fails closed without %s", async (name) => {
    vi.stubEnv(name, "");
    expect((await getPlaces(new Request(`${ORIGIN}/api/places`))).status).toBe(503);
    expect(upstream).toHaveLength(0);
  });
});

describe("guest session", () => {
  it("round-trips and gives the API a hash, not the cookie", async () => {
    answer = () => Response.json(reply);
    const cookie = issueSession();
    const res = await chatFree(post("/api/chat/free", { text: "ส้มตำ", history: [] }, { cookie: `she_session=${cookie}` }));
    expect(res.status).toBe(200);
    expect(header("x-she-session")).toMatch(/^[0-9a-f]{32}$/);
    expect(cookie).not.toContain(header("x-she-session")!);
  });

  it("rejects tampering, another secret and expiry", () => {
    const token = issueSession();
    const [id, exp, mac] = token.split(".");
    expect(readSession(token)).toMatch(/^[0-9a-f]{32}$/);
    for (const bad of [`${id}x.${exp}.${mac}`, `${id}.${Number(exp) + 1}.${mac}`, `${id}.${exp}.${"0".repeat(mac.length)}`, "", "a.b", "a.b.c.d"])
      expect(readSession(bad)).toBeNull();
    vi.stubEnv("SESSION_SECRET", "another-secret-another-secret-0123");
    expect(readSession(token)).toBeNull();
  });

  it("expires after 24 hours", () => {
    vi.useFakeTimers({ now: new Date("2026-11-24T00:00:00Z") });
    const token = issueSession();
    vi.setSystemTime(new Date("2026-11-24T23:59:59Z"));
    expect(readSession(token)).not.toBeNull();
    vi.setSystemTime(new Date("2026-11-25T00:00:01Z"));
    expect(readSession(token)).toBeNull();
  });

  it("never exposes the raw address and groups an IPv6 /64", () => {
    const of = (ip: string) => ipHash(new Headers({ "x-real-ip": ip }));
    expect(of("203.0.113.9")).toMatch(/^[0-9a-f]{32}$/);
    expect(of("203.0.113.9")).not.toBe(of("203.0.113.10"));
    expect(of("2001:db8:1:2:aaaa::1")).toBe(of("2001:db8:1:2:bbbb:cccc:dddd:2"));
    expect(of("2001:db8:1:2::1")).not.toBe(of("2001:db8:1:3::1"));
    expect(of("203.0.113.9")).not.toBe(createHash("sha256").update("203.0.113.9").digest("hex").slice(0, 32));
  });

  it("is issued only after Turnstile accepts the token", async () => {
    answer = () => Response.json({ success: true });
    const res = await createSession(post("/api/session", { token: "t" }));
    expect(res.status).toBe(204);
    const cookie = res.headers.get("set-cookie")!;
    for (const part of ["she_session=", "HttpOnly", "Secure", "SameSite=Lax", "Path=/", "Max-Age=86400"]) expect(cookie).toContain(part);
    expect(upstream[0].url).toBe("https://challenges.cloudflare.com/turnstile/v0/siteverify");
    expect(String(upstream[0].init.body)).not.toContain("203.0.113.9");
  });

  it.each([
    ["rejected", () => Response.json({ success: false })],
    ["odd answer", () => Response.json({ success: "true" })],
    ["server error", () => new Response("x", { status: 500 })],
    ["unreachable", () => Promise.reject(new Error("down"))],
  ])("gives no cookie when Turnstile is %s", async (_name, result) => {
    answer = result;
    const res = await createSession(post("/api/session", { token: "t" }));
    expect(res.status).toBeGreaterThanOrEqual(400);
    expect(res.headers.get("set-cookie")).toBeNull();
  });

  it("refuses Cloudflare's always-pass test secret in production", async () => {
    vi.stubEnv("VERCEL_ENV", "production");
    vi.stubEnv("TURNSTILE_SECRET_KEY", "1x0000000000000000000000000000000AA");
    answer = () => Response.json({ success: true });
    expect((await createSession(post("/api/session", { token: "t" }))).status).toBe(503);
  });
});

describe("chat", () => {
  const ok = { text: "ส้มตำ", history: [] };

  it("needs a session", async () => {
    expect((await chatFree(post("/api/chat/free", ok))).status).toBe(401);
    expect((await chatGuided(post("/api/chat/guided", {}))).status).toBe(401);
    expect(upstream).toHaveLength(0);
  });

  it.each([
    ["missing origin", { origin: null }], ["other origin", { origin: "https://evil.test" }], ["null origin", { origin: "null" }],
    ["cross-site fetch", { "sec-fetch-site": "cross-site" }],
  ])("blocks %s", async (_name, headers) => {
    expect((await chatFree(post("/api/chat/free", ok, { ...withCookie(), ...headers }))).status).toBe(403);
    expect(upstream).toHaveLength(0);
  });

  it("limits type, size and shape of the body", async () => {
    const send = (body: unknown, headers = {}) => chatFree(post("/api/chat/free", body, { ...withCookie(), ...headers }));
    expect((await send(ok, { "content-type": "text/plain" })).status).toBe(415);
    expect((await send({ text: "x".repeat(17000), history: [] })).status).toBe(413);
    expect((await send("{not json")).status).toBe(400);
    expect((await send({ text: "ก".repeat(501), history: [] })).status).toBe(400);
    expect((await send({ ...ok, extra: 1 })).status).toBe(400);
    expect(upstream).toHaveLength(0);
  });

  it("passes guided steps through", async () => {
    answer = () => Response.json({ state: { step: "place", answers: {}, error: null }, prompt: { text: "ที่ไหน", options: ["ขอนแก่น"] }, reply: null });
    const res = await chatGuided(post("/api/chat/guided", {}, withCookie()));
    expect((await res.json()).state.step).toBe("place");
  });

  it("is never cached", async () => {
    answer = () => Response.json(reply);
    expect((await chatFree(post("/api/chat/free", ok, withCookie()))).headers.get("cache-control")).toBe("no-store");
  });
});
