import type { z } from "zod";

interface Turnstile {
  render(element: HTMLElement, options: { sitekey: string; callback(token: string): void; "error-callback"(): void }): string;
  remove(id: string): void;
}
declare global {
  interface Window { turnstile?: Turnstile }
}

// Cloudflare's documented always-pass key; the server refuses its secret in production.
const SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "1x00000000000000000000AA";
const SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";

export class ChatProblem extends Error {}

const MESSAGES: Record<number, string> = {
  400: "ข้อความนี้ส่งไม่ได้ ลองพิมพ์ใหม่ให้สั้นลง",
  403: "ยืนยันว่าเป็นคนไม่สำเร็จ ลองโหลดหน้านี้ใหม่",
  429: "ส่งถี่เกินไป รอประมาณหนึ่งนาทีแล้วลองอีกครั้ง",
};
const UNAVAILABLE = "ระบบยังไม่พร้อม ลองอีกครั้งในอีกไม่กี่นาที";

function loadScript(): Promise<Turnstile> {
  if (window.turnstile) return Promise.resolve(window.turnstile);
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.onload = () => (window.turnstile ? resolve(window.turnstile) : reject(new Error("turnstile")));
    script.onerror = () => reject(new Error("turnstile"));
    document.head.append(script);
  });
}

async function startSession(widget: HTMLElement): Promise<void> {
  let token: string;
  try {
    const turnstile = await loadScript();
    token = await new Promise<string>((resolve, reject) => {
      const id = turnstile.render(widget, {
        sitekey: SITE_KEY,
        callback: (value) => { turnstile.remove(id); resolve(value); },
        "error-callback": () => { turnstile.remove(id); reject(new Error("turnstile")); },
      });
    });
  } catch {
    throw new ChatProblem(MESSAGES[403]);
  }
  const response = await post("/api/session", { token });
  if (!response.ok) throw new ChatProblem(MESSAGES[response.status] ?? UNAVAILABLE);
}

async function post(url: string, body: unknown): Promise<Response> {
  try {
    return await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  } catch {
    throw new ChatProblem(UNAVAILABLE);
  }
}

/** POST to a chat endpoint, verifying the visitor first when there is no session yet. */
export async function send<T extends z.ZodType>(schema: T, url: string, body: unknown, widget: HTMLElement): Promise<z.infer<T>> {
  let response = await post(url, body);
  if (response.status === 401) {
    await startSession(widget);
    response = await post(url, body);
  }
  if (!response.ok) throw new ChatProblem(MESSAGES[response.status] ?? UNAVAILABLE);
  const parsed = schema.safeParse(await response.json().catch(() => undefined));
  if (!parsed.success) throw new ChatProblem(UNAVAILABLE);
  return parsed.data;
}

export function problemText(error: unknown): string {
  return error instanceof ChatProblem ? error.message : UNAVAILABLE;
}
