import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

const users = JSON.parse(
  readFileSync("../../.local/demo-users.json", "utf8"),
) as { username: string; password: string }[];

for (const user of users) {
  test(`${user.username} signs in with fixed demo password only`, async ({
    page,
  }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Sign in securely" }).click();
    await page.locator("#username").fill(user.username);
    await page.locator("#password").fill(user.password);
    await page.locator("#kc-login").click();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    const me = await page.request.get("/api/v1/me");
    expect(me.status()).toBe(200);
    const account = await me.json();
    expect(account.role).toBe(
      user.username.startsWith("admin")
        ? "admin"
        : user.username.startsWith("reviewer")
          ? "reviewer"
          : user.username === "auditor"
            ? "auditor"
            : "institution_user",
    );
  });
}
