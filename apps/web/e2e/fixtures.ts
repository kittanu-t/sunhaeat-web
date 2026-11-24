import { test as base, expect } from "@playwright/test";

const BLANK_STYLE = {
  version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#dfe9f5" } }],
};

/** Blank map tiles, and a guard that fails any test with a CSP violation, page error or dialog. */
export const test = base.extend({
  page: async ({ page }, run) => {
    const problems: string[] = [];
    page.on("console", (m) => {
      if (/content security policy/i.test(m.text())) problems.push(m.text());
    });
    page.on("pageerror", (e) => problems.push(String(e)));
    page.on("dialog", (d) => {
      problems.push(`dialog ${d.message()}`);
      void d.dismiss();
    });
    await page.route("https://tiles.openfreemap.org/**", (route) => route.fulfill({ json: BLANK_STYLE }));
    await run(page);
    expect(problems).toEqual([]);
  },
});
export { expect };
