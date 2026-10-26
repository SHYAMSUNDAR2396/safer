import { expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { completeMfa } from "./mfa";
const users = JSON.parse(
  readFileSync("../../.local/demo-users.json", "utf8"),
) as { username: string; password: string }[];
export async function login(page: Page, name: string) {
  const u = users.find((x) => x.username === name)!;
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in securely" }).click();
  await page.locator("#password").waitFor();
  if (await page.getByRole("button", { name: "Restart login" }).isVisible()) {
    await page.getByRole("button", { name: "Restart login" }).click();
  }
  await page.locator("#username").fill(u.username);
  await page.locator("#password").fill(u.password);
  await page.locator("#kc-login").click();
  await completeMfa(page, name);
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  if (name === "reviewer" || name === "reviewer2") await loadReviewPages(page);
}

export async function loadReviewPages(page: Page) {
  const register = page.locator(".panel.register");
  await expect(register.locator("table, .empty")).toBeVisible();
  let pages = 0;
  while (
    await page
      .getByRole("button", { name: "Load more cases", exact: true })
      .isVisible()
  ) {
    if (++pages > 20)
      throw new Error(
        "Synthetic fixture inventory exceeds browser test page limit",
      );
    const before = await register.locator("tbody tr").count();
    await page
      .getByRole("button", { name: "Load more cases", exact: true })
      .click();
    await expect(async () => {
      const count = await register.locator("tbody tr").count();
      expect(
        count > before ||
          !(await page
            .getByRole("button", { name: /Load more cases|Loading more cases/ })
            .count()),
      ).toBe(true);
    }).toPass({ timeout: 15000 });
  }
}
export async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("link", { name: "Sign in securely" }),
  ).toBeVisible();
}
