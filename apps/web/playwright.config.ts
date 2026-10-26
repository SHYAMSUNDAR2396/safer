import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 120000, // Real TOTP replay prevention can require the next 30-second period.
  expect: { timeout: 10000 },
  reporter: [
    ["list"],
    ["junit", { outputFile: "../../.local/workflow-browser.xml" }],
  ],
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "only-on-failure",
  },
});
