import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e-readiness",
  workers: 1,
  timeout: 120000,
  expect: { timeout: 15000 },
  reporter: [
    ["list"],
    ["junit", { outputFile: "../../.local/readiness-browser.xml" }],
  ],
  use: {
    baseURL: process.env.SAFER_TEST_URL ?? "https://localhost:9443",
    headless: true,
    // Self-signed LOCAL test certificate; curl separately verifies its exact trust anchor.
    ignoreHTTPSErrors: true,
    screenshot: "only-on-failure",
  },
});
