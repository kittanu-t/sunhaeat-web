import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { isIPv6 } from "node:net";

export const SESSION_COOKIE = "she_session";
export const SESSION_SECONDS = 86_400;

function mac(purpose: string, value: string): string {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.length < 32) throw new Error("SESSION_SECRET must be at least 32 characters");
  return createHmac("sha256", secret).update(`${purpose}\n${value}`).digest("hex");
}

export function issueSession(): string {
  const body = `${randomBytes(16).toString("hex")}.${Math.floor(Date.now() / 1000) + SESSION_SECONDS}`;
  return `${body}.${mac("session", body)}`;
}

/** The hash the API sees for a valid session token, or null. */
export function readSession(token: string | undefined): string | null {
  const match = /^([0-9a-f]{32})\.(\d{10})\.([0-9a-f]{64})$/.exec(token ?? "");
  if (!match) return null;
  const [, id, expires, given] = match;
  if (!timingSafeEqual(Buffer.from(given), Buffer.from(mac("session", `${id}.${expires}`)))) return null;
  if (Number(expires) <= Date.now() / 1000) return null;
  return createHash("sha256").update(id).digest("hex").slice(0, 32);
}

export function sessionFrom(request: Request): string | null {
  const cookies = (request.headers.get("cookie") ?? "").split(";").map((c) => c.trim());
  return readSession(cookies.find((c) => c.startsWith(`${SESSION_COOKIE}=`))?.slice(SESSION_COOKIE.length + 1));
}

/** One subscriber usually controls a whole IPv6 /64, so limits apply to that. */
function subscriber(ip: string): string {
  if (!isIPv6(ip) || ip.includes(".")) return ip;
  const [head, tail] = ip.split("::");
  const left = head ? head.split(":") : [];
  const right = tail ? tail.split(":") : [];
  const gap = ip.includes("::") ? Array<string>(8 - left.length - right.length).fill("0") : [];
  return [...left, ...gap, ...right].slice(0, 4).map((g) => parseInt(g, 16).toString(16)).join(":");
}

export function ipHash(headers: Headers): string {
  // Vercel sets x-real-ip itself, so a client cannot choose it.
  return mac("ip", subscriber(headers.get("x-real-ip")?.trim() || "unknown")).slice(0, 32);
}
