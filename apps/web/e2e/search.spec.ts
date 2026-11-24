import AxeBuilder from "@axe-core/playwright";
import { BROKEN } from "../playwright.config";
import { expect, test } from "./fixtures";

const cards = "article[data-place]";

test("search by word and province shows the same places as cards and pins", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("searchbox").fill("ส้มตำ");
  await page.getByLabel("จังหวัด").selectOption("TH-40");
  await page.getByRole("button", { name: "ค้นหา", exact: true }).click();
  await expect(page).toHaveURL(/province=TH-40/);
  const results = page.getByRole("region", { name: "ผลการค้นหา" }).locator(cards);
  await expect(results).toHaveCount(2);
  const shown = await results.locator("h3").allInnerTexts();
  expect(shown).toContain("ร้านส้มตำระเบิด");
  await expect(page.locator("button[data-pin]")).toHaveCount(2);
  const pins = await page.locator("button[data-pin]").evaluateAll((all) => all.map((b) => b.getAttribute("aria-label")!));
  expect(pins.sort()).toEqual([...shown].sort());
});

test("a shared link restores the filters", async ({ page }) => {
  await page.goto("/?province=TH-30&tag=isan");
  await expect(page.getByLabel("จังหวัด")).toHaveValue("TH-30");
  await expect(page.getByRole("link", { name: "อีสาน/ส้มตำ" })).toHaveAttribute("aria-current", "true");
  await expect(page.getByRole("region", { name: "ผลการค้นหา" }).locator(cards)).toHaveCount(3);
});

test("choosing a pin focuses its card", async ({ page }) => {
  await page.goto("/?province=TH-30");
  const pin = page.locator("button[data-pin]").first();
  const name = await pin.getAttribute("aria-label");
  await pin.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(`${cards}:focus-within h3`)).toHaveText(name!);
});

test("refusing location explains and leaves search usable", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "ใกล้ฉัน" }).click();
  await expect(page.getByRole("status")).toContainText("ไม่ได้รับตำแหน่ง");
  await page.getByRole("searchbox").fill("กาแฟดอกคูน");
  await page.getByRole("button", { name: "ค้นหา", exact: true }).click();
  await expect(page.getByRole("region", { name: "ผลการค้นหา" }).locator(cards)).toHaveCount(1);
});

test("location stays out of the URL and is rounded before it leaves the page", async ({ page, context }) => {
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation({ latitude: 16.430123, longitude: 102.830456 });
  await page.goto("/");
  const sent = page.waitForRequest("**/api/near");
  await page.getByRole("button", { name: "ใกล้ฉัน" }).click();
  expect((await sent).postDataJSON()).toMatchObject({ lat: 16.43, lon: 102.83 });
  await expect(page.getByRole("region", { name: "ผลการค้นหา" }).locator(cards).first()).toContainText("ม.");
  expect(page.url()).not.toContain("16.43");
});

test("no match says so and offers a way out", async ({ page }) => {
  await page.goto("/?q=ไม่มีร้านชื่อนี้แน่นอน");
  await expect(page.getByText("ยังไม่พบร้าน")).toBeVisible();
  await expect(page.getByRole("link", { name: "ล้างตัวกรอง" })).toBeVisible();
});

test("markup in a restaurant name is plain text", async ({ page }) => {
  await page.goto("/?q=onerror");
  const card = page.getByRole("region", { name: "ผลการค้นหา" }).locator(cards);
  await expect(card.locator("h3")).toHaveText("<img src=x onerror=alert(1)> ส้มตำ");
  await expect(card.locator("img")).toHaveCount(0);
});

test("the list works without WebGL", async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, kind: string, ...rest: unknown[]) {
      return kind.startsWith("webgl") ? null : (original as (...a: unknown[]) => unknown).call(this, kind, ...rest);
    } as typeof original;
  });
  await page.goto("/?province=TH-30");
  await expect(page.getByText("อุปกรณ์นี้แสดงแผนที่ไม่ได้")).toBeVisible();
  await expect(page.getByRole("region", { name: "ผลการค้นหา" }).locator(cards)).toHaveCount(3);
});

test("fictional places are labelled and kept apart", async ({ page }) => {
  await page.goto("/");
  const strip = page.getByRole("region", { name: "ร้านตัวอย่าง" });
  await expect(strip.getByText("ร้านตัวอย่าง (สมมติ)").first()).toBeVisible();
  await expect(page.locator(`${cards}[data-demo="true"]`)).toHaveCount(await strip.locator(cards).count());
});

test("a dead API shows a status instead of an error page", async ({ page }) => {
  await page.goto(`${BROKEN}/`);
  await expect(page.getByText("ระบบค้นหายังไม่พร้อม")).toBeVisible();
  await page.goto(`${BROKEN}/r/demo-krua-dao-bueng`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("ครัวดาวบึงสมมติ");
  await expect(page.getByText("ร้านตัวอย่าง (สมมติ)").first()).toBeVisible();
});

for (const path of ["/", "/about"])
  test(`${path} has no serious accessibility problem or sideways scroll`, async ({ page }) => {
    await page.goto(path);
    const { violations } = await new AxeBuilder({ page }).analyze();
    const serious = violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
    expect(serious.map((v) => `${v.id}: ${v.nodes[0].html}`)).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  });
