import { NextRequest } from "next/server";
import { expect, it } from "vitest";
import { proxy } from "@/proxy";

const headers = () => proxy(new NextRequest("https://sunhaeat.test/")).headers;
const directive = (csp: string, name: string) => csp.split(";").map((d) => d.trim()).find((d) => d.startsWith(name + " ")) ?? "";

it("uses a fresh script nonce and no inline scripts", () => {
  const [a, b] = [headers().get("content-security-policy")!, headers().get("content-security-policy")!];
  const nonce = (csp: string) => /'nonce-([^']+)'/.exec(directive(csp, "script-src"))![1];
  expect(nonce(a)).not.toBe(nonce(b));
  expect(nonce(a).length).toBeGreaterThanOrEqual(22);
  expect(directive(a, "script-src")).not.toMatch(/unsafe-inline|unsafe-eval/);
});

it("limits where the page may connect, frame and submit", () => {
  const csp = headers().get("content-security-policy")!;
  expect(directive(csp, "default-src")).toBe("default-src 'self'");
  expect(directive(csp, "connect-src")).toBe("connect-src 'self' https://tiles.openfreemap.org");
  expect(directive(csp, "frame-src")).toBe("frame-src https://challenges.cloudflare.com");
  expect(directive(csp, "frame-ancestors")).toBe("frame-ancestors 'none'");
  expect(directive(csp, "object-src")).toBe("object-src 'none'");
  expect(directive(csp, "form-action")).toBe("form-action 'self'");
  expect(directive(csp, "base-uri")).toBe("base-uri 'none'");
});

it("sets the other security headers", () => {
  const h = headers();
  expect(h.get("strict-transport-security")).toContain("max-age=63072000");
  expect(h.get("x-content-type-options")).toBe("nosniff");
  expect(h.get("referrer-policy")).toBe("strict-origin-when-cross-origin");
  expect(h.get("permissions-policy")).toContain("geolocation=(self)");
});
