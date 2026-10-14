import { defineConfig, devices } from "@playwright/test";

const PORT = process.env.E2E_PORT ?? "3000";
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${PORT}`;

/** E2E smoke (Phase 7.2). Boots the built PWA and exercises the main routes. */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: `npm run start -- -p ${PORT}`,
        url: BASE_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
