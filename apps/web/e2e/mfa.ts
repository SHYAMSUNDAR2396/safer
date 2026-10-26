// Synthetic Keycloak enrollment helper. Secrets stay outside the checkout and .env.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import type { Page } from "@playwright/test";

function code(secret: string): string {
  return execFileSync(
    "../../.venv/bin/python",
    [
      "-c",
      "import sys,base64,time; from cryptography.hazmat.primitives.twofactor.totp import TOTP; from cryptography.hazmat.primitives.hashes import SHA1; key=sys.stdin.buffer.read(); print(TOTP(key,6,SHA1(),30).generate(time.time()).decode())",
    ],
    { input: secret, encoding: "utf8" },
  ).trim();
}

export async function completeMfa(page: Page, name: string) {
  await page
    .locator('[aria-label="Sign out"], input[name="totpSecret"], #otp')
    .first()
    .waitFor({ state: "attached" });
  if (await page.getByRole("button", { name: "Sign out" }).isVisible()) return;
  const directory = join(
    tmpdir(),
    `safer-readiness-${process.getuid?.() ?? "test"}`,
  );
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const path = join(directory, "synthetic-totp.json");
  let secrets: Record<string, string> = {};
  try {
    secrets = JSON.parse(readFileSync(path, "utf8"));
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e;
  }
  const enrolling =
    (await page.locator('input[name="totpSecret"]').count()) > 0;
  if (enrolling) {
    const secret = await page.locator('input[name="totpSecret"]').inputValue();
    await page.locator("#totp").fill(code(secret));
    const label = page.locator('input[name="userLabel"]');
    if (await label.count()) await label.fill("Synthetic test authenticator");
    await page.getByRole("button", { name: "Submit", exact: true }).click();
    await page.getByRole("button", { name: "Sign out" }).waitFor();
    secrets[name] = secret;
    writeFileSync(path, JSON.stringify(secrets), { mode: 0o600 });
  } else {
    if (!secrets[name])
      throw new Error(
        "Synthetic MFA enrollment secret is missing; do not reset a real user's factor.",
      );
    await page.locator("#otp").fill(code(secrets[name]));
    await page.getByRole("button", { name: /Sign In|Submit/i }).click();
    await page.waitForFunction(
      () =>
        !!document.querySelector('[aria-label="Sign out"]') ||
        document.querySelector("#otp")?.getAttribute("aria-invalid") === "true",
    );
    if (await page.locator('#otp[aria-invalid="true"]').count()) {
      // Keycloak rejects reuse of the same TOTP counter; wait for its real 30-second period.
      await page.waitForTimeout(31000 - (Date.now() % 30000));
      await page.locator("#otp").fill(code(secrets[name]));
      await page.getByRole("button", { name: /Sign In|Submit/i }).click();
    }
  }
}
