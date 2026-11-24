import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./fixtures";

test("a real place admits what is unknown and shows its source", async ({ page }) => {
  await page.goto("/?q=ส้มตำระเบิด");
  await page.getByRole("region", { name: "ผลการค้นหา" }).getByRole("link", { name: "ร้านส้มตำระเบิด" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("ร้านส้มตำระเบิด");
  for (const label of ["ราคา", "เวลาเปิด", "เมนู"])
    await expect(page.locator("dl > div", { has: page.locator(`dt:text-is("${label}")`) })).toContainText("ยังไม่มีข้อมูล");
  const text = await page.locator("main").innerText();
  expect(text).not.toMatch(/เปิดอยู่|อัปเดตล่าสุด/);
  expect(text).toContain("CDLA-Permissive-2.0");
  expect(text).toContain("e2e-release");
  await expect(page.getByRole("link", { name: "Facebook" })).toHaveAttribute("rel", /noopener/);
  await expect(page.getByText("ร้านตัวอย่าง (สมมติ)")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "แจ้งข้อมูลผิด" })).toBeVisible();
});

test("a demo place is labelled before its name and has a menu", async ({ page }) => {
  await page.goto("/r/demo-krua-dao-bueng");
  const badge = page.locator("main").getByText("ร้านตัวอย่าง (สมมติ)").first();
  const title = page.getByRole("heading", { level: 1 });
  expect((await badge.boundingBox())!.y).toBeLessThan((await title.boundingBox())!.y);
  await expect(page.getByText("ส้มตำไทย")).toBeVisible();
  await expect(page.locator("dl > div", { has: page.locator('dt:text-is("ราคา")') })).toContainText("45–90 บาท");
});

test("unknown places are a real 404", async ({ page }) => {
  expect((await page.goto("/r/no-such-place"))!.status()).toBe(404);
  expect((await page.goto("/r/..%2Fmeta"))!.status()).toBe(404);
});

test("place pages have no serious accessibility problem or sideways scroll", async ({ page }) => {
  await page.goto("/r/demo-krua-dao-bueng");
  const { violations } = await new AxeBuilder({ page }).analyze();
  const serious = violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  expect(serious.map((v) => `${v.id}: ${v.nodes[0].html}`)).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
});
