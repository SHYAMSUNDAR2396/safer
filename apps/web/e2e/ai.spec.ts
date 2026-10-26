import { expect, test } from "@playwright/test";

const base = {
  enabled: true,
  purpose: "summary",
  basis_sha256: "b".repeat(64),
  case_basis_sha256: "a".repeat(64),
  mode: "deterministic_fallback",
  reason: null,
  model: null,
  blocks: [
    {
      id: "b0",
      title: "Submitted FDR",
      text: "Institution-submitted claim.",
      facts: { Amount: "500000.00" },
      citations: [
        { kind: "submission", id: "synthetic-sub", href: "#submitted-claim" },
      ],
    },
  ],
};

test("explicit AI generation preserves facts and hides results on revoked access", async ({
  page,
}) => {
  let revoked = false;
  let posts = 0;
  await page.route("**/api/v1/reviews/synthetic-case/ai**", async (route) => {
    if (revoked)
      return route.fulfill({
        status: 404,
        json: { detail: "Case access revoked." },
      });
    if (route.request().method() === "POST") {
      posts++;
      expect(route.request().headers()["x-csrf-token"]).toBe("synthetic-csrf");
      return route.fulfill({
        json: {
          ...base,
          mode: "llm",
          model: "gemini-3.5-flash-lite",
          blocks: base.blocks.map((b) => ({
            ...b,
            ai_text: "Check the cited sources before resolving observations.",
          })),
        },
      });
    }
    return route.fulfill({ json: base });
  });
  await page.goto("/e2e/ai-harness.html");
  expect(posts).toBe(0);
  await page.getByRole("button", { name: "Summarize with AI" }).click();
  await expect(
    page.getByText("Check the cited sources before resolving observations."),
  ).toBeVisible();
  await expect(page.getByText("500000.00", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "submission · synthetic-sub" }),
  ).toHaveAttribute("href", "#submitted-claim");
  revoked = true;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByText("Check the cited sources before resolving observations."),
  ).toHaveCount(0);
  await expect(page.getByRole("alert")).toContainText("revoked");
  expect(posts).toBe(1);
});

test("fallback is labelled and changed source hides old draft", async ({
  page,
}) => {
  await page.route("**/api/v1/reviews/synthetic-case/ai**", (route) =>
    route.fulfill({ json: { ...base, reason: "disabled" } }),
  );
  await page.goto("/e2e/ai-harness.html");
  await page
    .getByRole("button", { name: "Explain discrepancies with AI" })
    .click();
  await expect(
    page.getByText("Local fallback · AI is switched off."),
  ).toBeVisible();
  await expect(page.getByText("500000.00", { exact: true })).toBeVisible();
  await page.evaluate(() =>
    (window as unknown as { renderAi: (basis: string) => void }).renderAi(
      "c".repeat(64),
    ),
  );
  await expect(page.getByText("500000.00", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText("changed");
});
