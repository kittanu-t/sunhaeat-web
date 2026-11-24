import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { issueSession } from "../src/lib/session";
import { expect, test } from "./fixtures";

const signIn = (page: Page) =>
  page.context().addCookies([{ name: "she_session", value: issueSession(), url: "http://localhost:3100", httpOnly: true, sameSite: "Lax" }]);
const lane = (page: Page, name: string) => page.getByRole("region", { name, exact: true }).locator("article[data-place]");
const REPLY = {
  mode: "rules", text: "ลองระบุจังหวัด", disclaimer: "d", partial: false, ai_unavailable: "limit", result: { matched: [], maybe: [], demo: [] },
  filters: { name: null, province_code: null, tags: [], terms: [], near: null, budget_per_person: null, needs_clarification: true },
};

async function ask(page: Page, text: string) {
  await page.getByLabel("ข้อความของคุณ").fill(text);
  await page.getByRole("button", { name: "ส่ง" }).click();
}

async function answer(page: Page, question: string, text: string) {
  await expect(page.getByRole("heading", { name: question })).toBeFocused();
  await page.getByLabel("คำตอบของคุณ").fill(text);
  await page.getByLabel("คำตอบของคุณ").press("Enter");
}

test.beforeEach(async ({ page }) => signIn(page));

test("guided mode works with the keyboard alone and separates the lanes", async ({ page }) => {
  await page.goto("/chat");
  await page.getByRole("tab", { name: "ตอบทีละข้อ" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "เริ่ม" }).focus();
  await page.keyboard.press("Enter");
  await answer(page, "อยากกินแถวไหน?", "ขอนแก่น");
  await answer(page, "ไปกันกี่คน?", "4");
  await answer(page, "งบต่อคนประมาณเท่าไร?", "100");
  await answer(page, "อยากกินอะไร?", "ส้มตำ");
  await answer(page, "มีข้อจำกัดไหม เช่น แพ้อาหารหรือฮาลาล?", "แพ้กุ้ง");
  await expect(page.getByText("งบรวมประมาณ 400 บาทสำหรับ 4 คน")).toBeVisible();
  await expect(page.getByText(/ต้องสอบถามร้านก่อน/)).toBeVisible();
  await expect(lane(page, "อาจตรง ไม่ทราบราคา")).toHaveCount(3);
  await expect(lane(page, "ร้านตัวอย่าง (สมมติ)")).toHaveCount(1);
  await expect(lane(page, "ตรงเงื่อนไข")).toHaveCount(0);
});

test("guided mode can pick an option, skip, go back and explain a bad answer", async ({ page }) => {
  await page.goto("/chat");
  await page.getByRole("tab", { name: "ตอบทีละข้อ" }).click();
  await page.getByRole("button", { name: "เริ่ม" }).click();
  await page.getByRole("button", { name: "ขอนแก่น" }).click();
  await answer(page, "ไปกันกี่คน?", "0");
  await expect(page.locator("main").getByRole("alert")).toContainText("1–50");
  await page.getByRole("button", { name: "ข้าม" }).click();
  await expect(page.getByRole("heading", { name: "งบต่อคนประมาณเท่าไร?" })).toBeFocused();
  await page.getByRole("button", { name: "ย้อนกลับ" }).click();
  await expect(page.getByRole("heading", { name: "ไปกันกี่คน?" })).toBeFocused();
});

test("free mode answers from rules and says AI was not used", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByText(/Google อาจนำไปปรับปรุงผลิตภัณฑ์/)).toBeVisible();
  await ask(page, "ส้มตำขอนแก่น");
  await expect(lane(page, "ตรงเงื่อนไข")).toHaveCount(3);
  await expect(page.getByText("คำตอบนี้มาจากกฎ ไม่ได้ใช้ AI")).toBeVisible();
});

test("a partly understood request is not labelled a full match", async ({ page }) => {
  await page.goto("/chat");
  await ask(page, "ส้มตำขอนแก่นที่มีห้องแอร์");
  await expect(lane(page, "ตรงเฉพาะบางเงื่อนไข")).toHaveCount(3);
  await expect(lane(page, "ตรงเงื่อนไข")).toHaveCount(0);
});

test("a verification that never answers gives up and frees the form", async ({ page, context }) => {
  await context.clearCookies();
  await page.clock.install();
  await page.route("https://challenges.cloudflare.com/**", (route) => route.fulfill({
    contentType: "text/javascript", body: "window.turnstile={render:()=>{window.rendered=true;return 'w'},remove(){}}",
  }));
  await page.goto("/chat");
  await ask(page, "ส้มตำขอนแก่น");
  await page.waitForFunction(() => (window as unknown as { rendered?: boolean }).rendered);
  await page.clock.fastForward(31_000);
  await expect(page.locator("main").getByRole("alert")).toContainText("ยืนยันว่าเป็นคนไม่สำเร็จ");
  await expect(page.getByRole("button", { name: "ส่ง" })).toBeEnabled();
});

test("switching modes keeps the conversation, reloading forgets it", async ({ page }) => {
  await page.goto("/chat");
  await ask(page, "ส้มตำขอนแก่น");
  await expect(lane(page, "ตรงเงื่อนไข")).toHaveCount(3);
  await page.getByRole("tab", { name: "ตอบทีละข้อ" }).click();
  await expect(lane(page, "ตรงเงื่อนไข")).toHaveCount(0);
  await page.getByRole("tab", { name: "คุยอิสระ" }).click();
  await expect(lane(page, "ตรงเงื่อนไข")).toHaveCount(3);
  await page.reload();
  await expect(page.getByText("ส้มตำขอนแก่น", { exact: true })).toHaveCount(0);
});

test("a finished quota is explained and guided mode still works", async ({ page }) => {
  await page.route("**/api/chat/free", (route) => route.fulfill({ json: REPLY }));
  await page.goto("/chat");
  await ask(page, "แนะนำหน่อย");
  await expect(page.getByText("โควตา AI วันนี้หมดแล้ว")).toBeVisible();
  await page.getByRole("tab", { name: "ตอบทีละข้อ" }).click();
  await page.getByRole("button", { name: "เริ่ม" }).click();
  await expect(page.getByRole("heading", { name: "อยากกินแถวไหน?" })).toBeVisible();
});

test("follow-ups send at most six earlier user messages", async ({ page }) => {
  const histories: string[][] = [];
  await page.route("**/api/chat/free", (route) => {
    histories.push(route.request().postDataJSON().history);
    return route.fulfill({ json: REPLY });
  });
  await page.goto("/chat");
  for (let i = 1; i <= 8; i++) {
    await ask(page, `ข้อความ ${i}`);
    await expect(page.getByText(`ข้อความ ${i}`, { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "ส่ง" })).toBeEnabled();
  }
  expect(histories[0]).toEqual([]);
  expect(histories[7]).toEqual([2, 3, 4, 5, 6, 7].map((i) => `ข้อความ ${i}`));
});

for (const [status, message] of [[429, "ส่งถี่เกินไป"], [503, "ระบบยังไม่พร้อม"]] as const)
  test(`a ${status} keeps the typed text and explains`, async ({ page }) => {
    await page.route("**/api/chat/free", (route) => route.fulfill({ status, json: { error: "x" } }));
    await page.goto("/chat");
    await ask(page, "ส้มตำขอนแก่น");
    await expect(page.locator("main").getByRole("alert")).toContainText(message);
    await expect(page.getByLabel("ข้อความของคุณ")).toHaveValue("ส้มตำขอนแก่น");
  });

test("without a session the visitor is verified once, then the message goes through", async ({ page, context }) => {
  await context.clearCookies();
  let verified = 0;
  await page.route("https://challenges.cloudflare.com/**", (route) => route.fulfill({
    contentType: "text/javascript",
    body: "window.turnstile={render:(el,o)=>{setTimeout(()=>o.callback('token'),0);return 'w'},remove(){}}",
  }));
  await page.route("**/api/session", async (route) => {
    verified++;
    expect(route.request().postDataJSON()).toEqual({ token: "token" });
    await signIn(page);
    await route.fulfill({ status: 204 });
  });
  await page.goto("/chat");
  await ask(page, "ส้มตำขอนแก่น");
  await expect(lane(page, "ตรงเงื่อนไข")).toHaveCount(3);
  await ask(page, "กาแฟขอนแก่น");
  await expect(lane(page, "ตรงเงื่อนไข")).toHaveCount(4);
  expect(verified).toBe(1);
});

test("chat has no serious accessibility problem or sideways scroll", async ({ page }) => {
  await page.goto("/chat");
  await ask(page, "ส้มตำขอนแก่น งบ 100");
  await expect(lane(page, "อาจตรง ไม่ทราบราคา")).toHaveCount(3);
  const { violations } = await new AxeBuilder({ page }).analyze();
  const serious = violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  expect(serious.map((v) => `${v.id}: ${v.nodes[0].html}`)).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
});
