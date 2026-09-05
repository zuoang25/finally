import { defineConfig, devices } from "@playwright/test";

/**
 * The suite always runs against the built container, never a dev server:
 *   - from the host:      http://localhost:8100 — the port docker-compose.test.yml
 *                         publishes, deliberately not 8000 so the suite never fights a
 *                         production `finally` container for the port
 *   - from the container: docker-compose.test.yml sets http://finally-test:8000
 *
 * Both halves read E2E_HOST_PORT, so overriding it moves the app and the tests together.
 */
const hostPort = process.env.E2E_HOST_PORT ?? "8100";
const baseURL = process.env.E2E_BASE_URL ?? `http://localhost:${hostPort}`;

export default defineConfig({
  testDir: "./specs",
  globalSetup: "./utils/global-setup.ts",

  // Specs mutate one shared SQLite book (cash, positions, watchlist), so they run
  // strictly in file-name order on a single worker. Retries are off on purpose: a
  // retry would replay trades against already-mutated state and could turn a real
  // defect into a green run.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,

  timeout: 90_000,
  expect: { timeout: 20_000 },

  reporter: process.env.CI
    ? [["list"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],

  use: {
    baseURL,
    actionTimeout: 20_000,
    navigationTimeout: 45_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1680, height: 1050 } },
    },
  ],
});
