import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests for the React (Vite) frontend.
 *
 * The Vite dev server proxies `/api/*` to the FastAPI backend on :8000, but
 * every test stubs `/api/v1/*` network calls with `page.route(...)`, so the
 * backend is never required — tests run fully in isolation and deterministically.
 *
 * Run with:
 *   npx playwright install chromium   (first time only)
 *   npm run test:e2e
 */
export default defineConfig({
  testDir: "./e2e",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? undefined : 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Optional: use an already-installed browser (e.g. Edge/Chrome) when the
    // Playwright-bundled Chromium can't be downloaded (network/DNS restrictions).
    // Set PW_CHANNEL=msedge (or chrome) to enable. Unsets to the bundled chromium.
    channel: process.env.PW_CHANNEL || undefined,
    // Video recording needs Playwright's bundled ffmpeg (which may fail to
    // download on restricted networks). Screenshots + traces are enough here.
    video: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // Add more browsers after `npx playwright install firefox webkit`:
    // { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    // { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: {
    command: "npm run dev -- --port 5173 --strictPort",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
