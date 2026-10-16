import { defineConfig } from "@playwright/test";

const PUERTO = 1425;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://localhost:${PUERTO}`,
    channel: "chrome",
    viewport: { width: 1280, height: 800 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: `npm run dev:mock -- --port ${PUERTO}`,
    url: `http://localhost:${PUERTO}`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
