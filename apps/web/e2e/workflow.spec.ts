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
async function submitCase(page: Page, ref: string, maturity = "2027-10-01") {
  await login(page, "alpha");
  await page.getByRole("button", { name: "New FDR" }).click();
  await page.getByLabel("Bank name").fill("Synthetic Review Bank");
  await page.getByLabel("FDR reference").fill(ref);
  await page.getByLabel("Principal amount (INR)").fill("250000.00");
  await page.getByLabel("Issue date").fill("2026-10-01");
  await page.getByLabel("Maturity date").fill(maturity);
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

test("renewed FDR replaces the old one only after reviewer acceptance", async ({
  page,
}) => {
  const stamp = Date.now();
  const oldRef = `OLD-${stamp}`;
  const newRef = `NEW-${stamp}`;
  await submitCase(page, oldRef);
  await submitCase(page, newRef, "2028-10-01");
  await login(page, "alpha");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  const option = page.locator("option", { hasText: newRef });
  await page
    .getByLabel("Renewed or replacement FDR")
    .selectOption((await option.getAttribute("value"))!);
  await page.getByRole("button", { name: "Propose as replacement" }).click();
  await expect(page.getByText("Proposed · awaiting reviewer")).toBeVisible();
  await expect(
    page.locator(".doc-list.chain li", { hasText: newRef }),
  ).toContainText("Proposed replacement · not yet cover");
  await signOut(page);
  await login(page, "reviewer");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  await page.getByRole("button", { name: "Accept replacement" }).click();
  await expect(
    page.getByText(/Accepted by Regulation Bureau reviewer/),
  ).toBeVisible();
  await signOut(page);
  await login(page, "alpha");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  await expect(
    page.locator(".doc-list.chain li", { hasText: oldRef }),
  ).toContainText("Replaced");
  await expect(
    page.locator(".doc-list.chain li", { hasText: newRef }),
  ).toContainText("Counts as cover");
  await expect(page.getByText("Settled · replacement accepted")).toBeVisible();
  await page.screenshot({
    path: "test-results/replacement.png",
    fullPage: true,
  });
});

test("release authority needs a second administrator and grants take effect immediately", async ({
  page,
}) => {
  const reviewer2 = "Second Bureau reviewer";
  await login(page, "admin1");
  await expect(
    page.getByRole("heading", { name: "Authority and delegation" }),
  ).toBeVisible();
  // Grants persist between runs: clear reviewer2's live grants first.
  await expect(
    page
      .locator("section", {
        has: page.getByRole("heading", { name: "All grants" }),
      })
      .locator(".grant")
      .first(),
  ).toBeVisible();
  const live = page.locator(".grant", { hasText: reviewer2 }).filter({
    has: page.getByRole("button", { name: /Revoke|Withdraw/ }),
  });
  while ((await live.count()) > 0) {
    const before = await live.count();
    await live
      .first()
      .getByRole("button", { name: /Revoke|Withdraw/ })
      .click();
    await expect(live).toHaveCount(before - 1);
  }
  const form = page.locator("form");
  await form.getByLabel("Reviewer").selectOption({ label: reviewer2 });
  await form.getByLabel("Authority").selectOption("release_approve");
  await form
    .getByLabel("Institution")
    .selectOption({ label: "Alpha Technical Institute" });
  await form.getByLabel("Reason").fill("Release cover for Alpha");
  await page
    .getByRole("button", { name: "Request (needs second approval)" })
    .click();
  const pendingRow = page
    .locator(".grant", { hasText: "Release cover for Alpha" })
    .first();
  await expect(pendingRow).toContainText("Awaiting second administrator");
  await expect(pendingRow).toContainText("Another administrator must approve");
  await form.getByLabel("Authority").selectOption("review");
  await form.getByLabel("Reason").fill("Review cover for Alpha");
  await page.getByRole("button", { name: "Grant authority" }).click();
  await expect(
    page.locator(".grant", { hasText: "Review cover for Alpha" }).first(),
  ).toContainText("Active");
  await signOut(page);

  await login(page, "admin2");
  await page
    .locator(".grant", { hasText: "Release cover for Alpha" })
    .first()
    .getByRole("button", { name: "Approve" })
    .click();
  await expect(
    page.locator(".grant", { hasText: "Release cover for Alpha" }).first(),
  ).toContainText("approved by Access administrator two");
  await page.screenshot({
    path: "test-results/access.png",
    fullPage: true,
  });
  await signOut(page);

  await login(page, "reviewer2");
  await expect(
    page.getByRole("heading", { name: "Cases awaiting review" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /^REVIEW-/ }).first(),
  ).toBeVisible();
  await signOut(page);

  await login(page, "admin1");
  await page
    .locator(".grant", { hasText: "Review cover for Alpha" })
    .first()
    .getByRole("button", { name: "Revoke" })
    .click();
  await signOut(page);
  await login(page, "reviewer2");
  await expect(page.getByText("No cases waiting")).toBeVisible();
});

test("a policy draft is published only by a second administrator", async ({
  page,
}) => {
  const note = `Policy check ${Date.now()}`;
  await login(page, "admin1");
  await page.getByText("Draft a new version").click();
  await page.getByLabel("Audit confirmation").check();
  await page.getByLabel("Note", { exact: true }).fill(note);
  await page.getByRole("button", { name: "Save draft version" }).click();
  const row = page.locator(".grant", { hasText: note });
  await expect(row).toContainText("Draft");
  await expect(row).toContainText("Another administrator must publish");
  await signOut(page);
  await login(page, "admin2");
  await page
    .locator(".grant", { hasText: note })
    .getByRole("button", { name: "Publish" })
    .click();
  await expect(page.locator(".grant", { hasText: note })).toContainText(
    "published by Access administrator two",
  );
  await expect(page.locator(".grant", { hasText: note })).toContainText(
    "not validated by the policy owner",
  );
});

async function ensureReleaseAuthority(page: Page) {
  await login(page, "admin1");
  const grants = page.locator("section", {
    has: page.getByRole("heading", { name: "All grants" }),
  });
  await expect(grants.locator(".grant").first()).toBeVisible();
  const held = grants
    .locator(".grant", { hasText: "Second Bureau reviewer · Release approval" })
    .filter({ hasText: "Active" });
  if ((await held.count()) === 0) {
    const pendingOwn = page
      .locator("section", {
        has: page.getByRole("heading", { name: "Awaiting approval" }),
      })
      .locator(".grant", { hasText: "Second Bureau reviewer" });
    if ((await pendingOwn.count()) === 0) {
      const form = page.locator("form");
      await form
        .getByLabel("Reviewer")
        .selectOption({ label: "Second Bureau reviewer" });
      await form.getByLabel("Authority").selectOption("release_approve");
      await form
        .getByLabel("Institution")
        .selectOption({ label: "Alpha Technical Institute" });
      await form.getByLabel("Reason").fill("Release cover for Alpha");
      await page
        .getByRole("button", { name: "Request (needs second approval)" })
        .click();
      await expect(pendingOwn.first()).toBeVisible();
    }
    await signOut(page);
    await login(page, "admin2");
    await page
      .locator("section", {
        has: page.getByRole("heading", { name: "Awaiting approval" }),
      })
      .locator(".grant", { hasText: "Second Bureau reviewer" })
      .first()
      .getByRole("button", { name: "Approve" })
      .click();
    await expect(
      page.getByText("Nothing is waiting for approval."),
    ).toBeVisible();
  }
  await signOut(page);
}

test("replaced FDR is released after clearances and a competent decision", async ({
  page,
}) => {
  test.setTimeout(90000);
  await ensureReleaseAuthority(page);
  const stamp = Date.now();
  const oldRef = `REL-OLD-${stamp}`;
  const newRef = `REL-NEW-${stamp}`;
  await submitCase(page, oldRef);
  await submitCase(page, newRef, "2028-10-01");
  await login(page, "alpha");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  const option = page.locator("option", { hasText: newRef });
  await page
    .getByLabel("Renewed or replacement FDR")
    .selectOption((await option.getAttribute("value"))!);
  await page.getByRole("button", { name: "Propose as replacement" }).click();
  await signOut(page);
  await login(page, "reviewer");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  await page.getByRole("button", { name: "Accept replacement" }).click();
  await expect(page.getByText(/Accepted by/)).toBeVisible();
  await signOut(page);

  await login(page, "alpha");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  await page
    .getByLabel("Reason for release")
    .fill("Cover moved to the renewed FDR");
  await page.getByRole("button", { name: "Request release" }).click();
  await expect(
    page.locator(".release-card").getByText("Open · clearances in progress"),
  ).toBeVisible();
  await signOut(page);

  await login(page, "reviewer");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  const card = page.locator(".release-card");
  for (let i = 0; i < 2; i++) {
    await card.getByLabel("Note for this action").fill("Original received");
    await card
      .getByRole("button", { name: "Record clearance" })
      .first()
      .click();
    await expect(
      card.getByText("cleared by Regulation Bureau reviewer"),
    ).toHaveCount(i + 1);
  }
  await signOut(page);

  await login(page, "reviewer2");
  const decision = page.locator(".release-card", { hasText: oldRef }).first();
  await decision.getByLabel("Note for this action").fill("Clearances complete");
  await page.screenshot({
    path: "test-results/release.png",
    fullPage: true,
  });
  await decision.getByRole("button", { name: "Approve release" }).click();
  const approved = page.locator(".release-card", { hasText: oldRef }).first();
  await expect(approved).toContainText("Approved");
  await approved
    .getByLabel("Note for this action")
    .fill("Lien release and refund");
  await approved
    .getByRole("button", { name: "Issue release instruction" })
    .click();
  // Instructed requests leave the approver's queue.
  await expect(page.locator(".release-card", { hasText: oldRef })).toHaveCount(
    0,
  );
  await signOut(page);

  await login(page, "reviewer");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  const live = page.locator(".release-card");
  await expect(live).toContainText("SAFER-REL-");
  await live.getByText("Record the bank's execution evidence").click();
  await live.getByLabel("Bank transaction reference").fill("UTR-E2E-0001");
  await live
    .getByLabel("Source (bank, branch or contact)")
    .fill("Synthetic Review Bank, Fort branch");
  await live.getByLabel("Evidence note").fill("Credit advice received");
  await live.getByRole("button", { name: "Record execution evidence" }).click();
  await expect(live).toContainText("executed amount matches the instruction");
  await live.getByLabel("Note for this action").fill("Reconciled");
  await live.getByRole("button", { name: "Close case" }).click();
  await expect(live).toContainText("Closed · executed and reconciled");
  await page.screenshot({
    path: "test-results/release-closed.png",
    fullPage: true,
  });
  await signOut(page);

  await login(page, "alpha");
  await page.getByRole("button", { name: oldRef, exact: true }).click();
  await expect(page.locator(".release-card")).toContainText(
    "Closed · executed and reconciled",
  );
  await expect(page.locator(".release-card")).toContainText(
    "Approved · Second Bureau reviewer",
  );
  await expect(page.locator(".page-heading .badge")).toContainText("Closed");
});
