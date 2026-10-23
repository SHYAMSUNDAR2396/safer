import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

const users = JSON.parse(
  readFileSync("../../.local/demo-users.json", "utf8"),
) as { username: string; password: string }[];
function minimalPdf() {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets = objects.map((o, i) => {
    const at = body.length;
    body += `${i + 1} 0 obj\n${o}\nendobj\n`;
    return at;
  });
  const xref = body.length;
  body += `xref\n0 4\n0000000000 65535 f \n${offsets
    .map((o) => `${String(o).padStart(10, "0")} 00000 n \n`)
    .join("")}trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "latin1");
}
async function login(page: Page, name: string) {
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
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
}
async function submitCase(page: Page, ref: string) {
  await login(page, "alpha");
  await page.getByRole("button", { name: "New FDR" }).click();
  await page.getByLabel("Bank name").fill("Synthetic Review Bank");
  await page.getByLabel("FDR reference").fill(ref);
  await page.getByLabel("Principal amount (INR)").fill("250000.00");
  await page.getByLabel("Issue date").fill("2026-10-01");
  await page.getByLabel("Maturity date").fill("2027-10-01");
  await page.getByRole("button", { name: "Save draft" }).click();
  await page.getByLabel("Upload document").setInputFiles({
    name: "review-fdr.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdf(),
  });
  await page.getByRole("button", { name: "Submit metadata" }).click();
  await page.getByRole("button", { name: "Confirm submission" }).click();
  await expect(
    page.getByText("Metadata submitted", { exact: true }),
  ).toBeVisible();
  await signOut(page);
}
async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("link", { name: "Sign in securely" }),
  ).toBeVisible();
}

test("institution creates, edits, submits and reloads an audited record", async ({
  page,
}) => {
  await login(page, "alpha");
  await page.getByRole("button", { name: "New FDR" }).click();
  await page.getByLabel("Bank name").fill("Synthetic Test Bank");
  const ref = `E2E-${Date.now()}`;
  await page.getByLabel("FDR reference").fill(ref);
  await page.getByLabel("Principal amount (INR)").fill("125000.25");
  await page.getByLabel("Issue date").fill("2026-10-01");
  await page.getByLabel("Maturity date").fill("2027-10-01");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("heading", { name: ref })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Submit metadata" }),
  ).toBeDisabled();
  await expect(page.getByText("Before submitting, upload")).toContainText(
    "FDR certificate",
  );
  await expect(page.getByLabel("Document type")).toHaveValue("fdr_certificate");
  await page.screenshot({
    path: "test-results/draft-requirements.png",
    fullPage: true,
  });
  await page.getByLabel("Upload document").setInputFiles({
    name: "synthetic-fdr-receipt.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdf(),
  });
  await expect(page.getByText("Scanned clean", { exact: true })).toBeVisible({
    timeout: 20000,
  });
  await expect(
    page.getByText("Malware scan completed", { exact: true }),
  ).toBeVisible();
  const downloading = page.waitForEvent("download");
  await page
    .getByRole("link", { name: "Download synthetic-fdr-receipt.pdf" })
    .click();
  const file = await downloading;
  expect(file.suggestedFilename()).toBe("synthetic-fdr-receipt.pdf");
  expect(readFileSync(await file.path())).toEqual(minimalPdf());
  await expect(
    page.getByRole("button", { name: "Submit metadata" }),
  ).toBeEnabled();
  await page.getByLabel("Upload document").setInputFiles({
    name: "renamed.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("plain text pretending to be a PDF"),
  });
  await expect(page.getByRole("alert")).toContainText("PDF, JPEG or PNG");
  await expect(page.getByText("renamed.pdf")).toHaveCount(0);
  await page.getByRole("button", { name: "Edit draft" }).click();
  await page.getByLabel("Principal amount (INR)").fill("130000.50");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Draft updated", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Submit metadata" }).click();
  await page.getByRole("button", { name: "Confirm submission" }).click();
  await expect(
    page.getByText("Metadata submitted", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit draft" })).toHaveCount(0);
  await expect(page.getByLabel("Upload document")).toHaveCount(0);
  await expect(page.getByText("synthetic-fdr-receipt.pdf")).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: ref, exact: true }).click();
  await expect(
    page.getByText("Metadata submitted", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/submitted-record.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("link", { name: "Sign in securely" }),
  ).toBeVisible();
});

test("another institution cannot see alpha records and auditor cannot create", async ({
  page,
}) => {
  await login(page, "beta");
  await expect(
    page.getByText("Beta Technical Institute", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /E2E-/ })).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByRole("link", { name: "Sign in securely" }),
  ).toBeVisible();
  await login(page, "auditor");
  await expect(
    page.getByText("Read-only access", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "New FDR" })).toHaveCount(0);
});

test("failed save preserves entered data and mobile register fits viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "alpha");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "New FDR" }).click();
  await page.getByLabel("Bank name").fill("Keep this bank");
  await page.getByLabel("FDR reference").fill("UNSAVED");
  await page.getByLabel("Principal amount (INR)").fill("100.00");
  await page.getByLabel("Issue date").fill("2026-10-01");
  await page.getByLabel("Maturity date").fill("2027-10-01");
  await page.route("**/api/v1/instruments", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({
          status: 503,
          contentType: "application/problem+json",
          body: JSON.stringify({ detail: "Storage temporarily unavailable." }),
        })
      : route.continue(),
  );
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Storage temporarily unavailable",
  );
  await expect(page.getByLabel("Bank name")).toHaveValue("Keep this bank");
  await page.screenshot({
    path: "test-results/mobile-form.png",
    fullPage: true,
  });
});

test("expired session recovers without losing form data", async ({
  page,
  context,
}) => {
  await login(page, "alpha");
  await page.getByRole("button", { name: "New FDR" }).click();
  await page.getByLabel("Bank name").fill("Recovery Bank");
  const reference = `RECOVERY-${Date.now()}`;
  await page.getByLabel("FDR reference").fill(reference);
  await page.getByLabel("Principal amount (INR)").fill("100.00");
  await page.getByLabel("Issue date").fill("2026-10-01");
  await page.getByLabel("Maturity date").fill("2027-10-01");
  // Revokes the real server session, exercising the same 401 boundary as expiry.
  const other = await context.newPage();
  await other.goto("/");
  await other.getByRole("button", { name: "Sign out" }).click();
  await expect(
    other.getByRole("link", { name: "Sign in securely" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Sign in again in a new tab" }),
  ).toBeVisible();
  await login(other, "alpha");
  await expect(page.getByLabel("Bank name")).toHaveValue("Recovery Bank");
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByRole("heading", { name: reference })).toBeVisible();
  await other.close();
});

test("reviewer compares evidence and resolves an observation with the institution", async ({
  page,
}) => {
  const ref = `REVIEW-${Date.now()}`;
  await submitCase(page, ref);
  await login(page, "reviewer");
  await expect(
    page.getByRole("heading", { name: "Cases awaiting review" }),
  ).toBeVisible();
  await page.getByRole("button", { name: ref, exact: true }).click();
  for (const [field, value, result] of [
    ["Principal amount", "250000.00", "Match"],
    ["Maturity date", "2027-09-30", "Mismatch"],
  ]) {
    await page.getByRole("button", { name: "Record evidence" }).click();
    await page.getByLabel("Field").selectOption({ label: field });
    await page.getByLabel("Value confirmed by the bank").fill(value);
    await page
      .getByLabel("Source (bank, branch or contact)")
      .fill("Synthetic Review Bank, Fort branch");
    await page.getByRole("button", { name: "Record evidence" }).last().click();
    await expect(
      page.getByRole("row", { name: new RegExp(field) }),
    ).toContainText(result);
  }
  await page.getByRole("button", { name: "Raise observation" }).click();
  await page.getByLabel("Concerning").selectOption({ label: "Maturity date" });
  await page
    .getByRole("textbox", { name: "Observation" })
    .fill("The bank confirms maturity on 30 Sep 2027.");
  await page.getByRole("button", { name: "Raise observation" }).last().click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.locator(".thread").getByText("The bank confirms maturity"),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/review-case.png",
    fullPage: true,
  });
  await signOut(page);

  await login(page, "alpha");
  await page.getByRole("button", { name: ref, exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Reviewer observations" }),
  ).toBeVisible();
  await page.getByLabel("Your response").fill("We will obtain a bank letter.");
  await page.getByRole("button", { name: "Send reply" }).click();
  await expect(page.getByText("We will obtain a bank letter.")).toBeVisible();
  await signOut(page);

  await login(page, "reviewer");
  await page.getByRole("button", { name: ref, exact: true }).click();
  await page.getByLabel("Reply or resolve").fill("Accepted after branch call.");
  await page.getByRole("button", { name: "Resolve" }).click();
  await expect(page.getByText("Resolved", { exact: true })).toBeVisible();
  await expect(page.getByText("Observation resolved")).toBeVisible();
});

test("simulated bank answer is labelled and compared without counting as confirmation", async ({
  page,
}) => {
  const ref = `SIM-${Date.now()}-MISMATCH`;
  await submitCase(page, ref);
  await login(page, "reviewer");
  await page.getByRole("button", { name: ref, exact: true }).click();
  await expect(
    page.getByText("SIMULATED BANK · NOT A REAL BANK"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Request simulated confirmation" })
    .click();
  await expect(page.getByRole("row", { name: /Maturity date/ })).toContainText(
    "Mismatch · simulated",
  );
  await expect(
    page.getByRole("row", { name: /Principal amount/ }),
  ).toContainText("Match · simulated");
  await expect(
    page.getByText("Answered · values recorded as simulated evidence"),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/bank-simulator.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Back to review queue" }).click();
  await expect(page.getByRole("row", { name: new RegExp(ref) })).toContainText(
    "0 of 5 confirmed",
  );
});

test("overdue renewal shows separate dates and escalates to the assigned reviewer", async ({
  page,
}) => {
  test.setTimeout(150000); // the scheduler sweeps once a minute
  const iso = (days: number) =>
    new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);
  const ref = `DUE-${Date.now()}`;
  await login(page, "alpha");
  await page.getByRole("button", { name: "New FDR" }).click();
  await page.getByLabel("Bank name").fill("Synthetic Deadline Bank");
  await page.getByLabel("FDR reference").fill(ref);
  await page.getByLabel("Principal amount (INR)").fill("90000.00");
  await page.getByLabel("Issue date").fill(iso(-200));
  await page.getByLabel("Maturity date").fill(iso(10));
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(
    page.getByRole("heading", { name: "Deadlines and reminders" }),
  ).toBeVisible();
  await expect(page.getByText("Until formally released")).toBeVisible();
  await page.getByLabel("Upload document").setInputFiles({
    name: "deadline-fdr.pdf",
    mimeType: "application/pdf",
    buffer: minimalPdf(),
  });
  await page.getByRole("button", { name: "Submit metadata" }).click();
  await page.getByRole("button", { name: "Confirm submission" }).click();
  await expect(
    page.getByText("Metadata submitted", { exact: true }),
  ).toBeVisible();
  await expect(async () => {
    await page.reload();
    await page.getByRole("button", { name: ref, exact: true }).click();
    await expect(
      page.locator(".reminder.escalation").getByText("Escalated to reviewer"),
    ).toBeVisible({ timeout: 2000 });
  }).toPass({ timeout: 100000, intervals: [5000] });
  await expect(page.locator(".reminder.action_due")).toContainText(
    "Renew or replace this FDR",
  );
  await expect(async () => {
    await page.reload();
    await page.getByRole("button", { name: ref, exact: true }).click();
    await expect(
      page
        .locator(".reminder.action_due")
        .getByText("Email to Alpha institution officer: sent"),
    ).toBeVisible({ timeout: 2000 });
  }).toPass({ timeout: 60000, intervals: [3000] });
  await page.getByRole("button", { name: /Notifications, [1-9]/ }).click();
  const inbox = page.getByRole("region", { name: "Notifications" });
  await expect(
    inbox.locator("li", { hasText: ref }).getByText("Renewal action due"),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/deadlines.png",
    fullPage: true,
  });
  await inbox
    .locator("li", { hasText: ref })
    .getByRole("button", { name: "Mark as read" })
    .click();
  await expect(
    inbox.locator("li", { hasText: ref }).getByRole("button", {
      name: "Mark as read",
    }),
  ).toHaveCount(0);
  await signOut(page);
  await login(page, "reviewer");
  await page.getByRole("button", { name: /Notifications/ }).click();
  await expect(
    page
      .getByRole("region", { name: "Notifications" })
      .locator("li", { hasText: ref }),
  ).toContainText("Escalated to reviewer");
  await expect(page.getByRole("row", { name: new RegExp(ref) })).toContainText(
    "Escalated",
  );
  await page.getByRole("button", { name: ref, exact: true }).click();
  await expect(page.locator(".reminder.escalation")).toContainText(
    "Owner: Regulation Bureau reviewer",
  );
});
