import { defineConfig, devices } from "@playwright/test";

process.env.SESSION_SECRET = "e2e-session-secret-e2e-session-secret";
const env = (api: string) => ({
  API_BASE_URL: api,
  API_HMAC_SECRET: "e2e-hmac-secret",
  SESSION_SECRET: process.env.SESSION_SECRET!,
  TURNSTILE_SECRET_KEY: "1x0000000000000000000000000000000AA",
});

export const WORKING = "http://localhost:3100";
export const BROKEN = "http://localhost:3101"; // its API address answers nothing

export default defineConfig({
  testDir: "e2e",
  workers: 2,
  retries: 0,
  use: {
    baseURL: WORKING,
    locale: "th-TH",
    launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] },
  },
  projects: [
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 375, height: 812 } } },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
  ],
  webServer: [
    {
      command: "uv run --directory ../api python -m testsupport.e2e_server 8011",
      env: { PYTHONPATH: process.platform === "win32" ? ".;../.." : ".:../.." },
      url: "http://127.0.0.1:8011/healthz",
      timeout: 90_000,
    },
    { command: "npx next start -p 3100", env: env("http://127.0.0.1:8011"), url: `${WORKING}/about` },
    { command: "npx next start -p 3101", env: env("http://127.0.0.1:9"), url: `${BROKEN}/about` },
  ],
});
