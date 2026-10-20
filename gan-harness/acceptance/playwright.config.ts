import { defineConfig, devices } from "@playwright/test";

/**
 * UI acceptance suite. BASE_URL is the console, API_URL the Asteria API; both
 * must already be running (see README "Run"). Never a hardcoded host.
 *
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE is only for machines with a pre-installed
 * Chromium; normally `npx playwright install chromium` provides the browser.
 */
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined;

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  timeout: 60_000,
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://127.0.0.1:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
        launchOptions: {
          executablePath,
          // WebGL for the Cesium globe in headless Chromium.
          args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
        },
      },
    },
  ],
});
