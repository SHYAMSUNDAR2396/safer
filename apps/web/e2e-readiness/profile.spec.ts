import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { login, signOut } from "../e2e/auth";

test("local HTTPS encrypted-bucket submission and privileged TOTP review", async ({
  page,
}) => {
  await login(page, "alpha");
  const ref = `SYNTHETIC-READY-${Date.now()}`;
  await page.getByRole("button", { name: "New FDR" }).click();
  await page.getByLabel("Bank name").fill("Synthetic Readiness Bank");
  await page.getByLabel("FDR reference").fill(ref);
  await page.getByLabel("Principal amount (INR)").fill("123456.78");
  await page.getByLabel("Issue date").fill("2026-01-01");
  await page.getByLabel("Maturity date").fill("2028-01-01");
  await page.getByRole("button", { name: "Save draft" }).click();
  const pdf = execFileSync("../../.venv/bin/python", [
    "-c",
    "import sys,io; from pypdf import PdfWriter; w=PdfWriter(); w.add_blank_page(width=200,height=200); b=io.BytesIO(); w.write(b); sys.stdout.buffer.write(b.getvalue())",
  ]);
  await page.getByLabel("Upload document").setInputFiles({
    name: "synthetic-encrypted-receipt.pdf",
    mimeType: "application/pdf",
    buffer: pdf,
  });
  await expect(page.getByText("Scanned clean", { exact: true })).toBeVisible({
    timeout: 30000,
  });
  await page.getByRole("button", { name: "Submit metadata" }).click();
  await page.getByRole("button", { name: "Confirm submission" }).click();
  await expect(
    page.getByText("Metadata submitted", { exact: true }),
  ).toBeVisible();
  const cookies = await page.context().cookies();
  expect(cookies.find((c) => c.name === "safer_session")?.secure).toBe(true);
  await signOut(page);
  await login(page, "reviewer");
  await page.getByRole("button", { name: ref, exact: true }).click();
  await page
    .getByRole("button", { name: "Generate case summary", exact: true })
    .click();
  await expect(page.locator(".case-summary")).toContainText("123456.78");
  await page.screenshot({
    path: "test-results/readiness-case.png",
    fullPage: true,
  });
});

test("register and new-record dialog pass automated accessibility checks", async ({
  page,
}) => {
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  await login(page, "alpha");
  const register = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(register.violations).toEqual([]);
  await page.getByRole("button", { name: "New FDR" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  const form = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(form.violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
