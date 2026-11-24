// Screenshots of a running site: node scripts/shots.mjs http://localhost:3200 out-dir [path=name ...]
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "@playwright/test";

const [base, out, ...pages] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
for (const [size, viewport] of Object.entries({ phone: { width: 375, height: 812 }, desktop: { width: 1440, height: 900 } })) {
  const page = await browser.newPage({ viewport, locale: "th-TH" });
  page.on("console", (m) => { if (["error", "warning"].includes(m.type())) console.log(size, m.text().slice(0, 300)); });
  for (const entry of pages) {
    const [path, name] = entry.split("=>");
    await page.goto(base + path, { waitUntil: "load" });
    await page.waitForTimeout(5000); // let map tiles draw
    await page.screenshot({ path: join(out, `${name}-${size}.png`) });
  }
  await page.close();
}
await browser.close();
