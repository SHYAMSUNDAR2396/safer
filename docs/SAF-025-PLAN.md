# SAF-025 plan and ledger

Scope: concise reviewer case summaries from authorized structured facts, resolvable citations, material-change invalidation and independent disable. Builds on the user-selected local fallback in SAF-024. No AI service, model claim or external transfer.

Ruling: use versioned deterministic summary templates and a stateless source-basis digest rather than a new database/cache. Browser-held snapshots become visibly stale and hide old facts when case basis changes or revalidation finds a mismatch. No summary is approval evidence. Cost: no server-side summary history and no generated model wording; those require a separate future scope.

1. RED: API tests for exact amounts/dates, citations, material evidence/observation changes, unchanged reads, scope/revocation, independently disabled summaries and instruction-like data.
2. Backend: explicit source projection/digest, independent flag, source-state in case response and read-only summary/revalidation endpoint.
3. Browser RED then GREEN: generate, inspect citations, modify evidence and verify stale summary hides facts until regeneration; bounded revalidation on focus and interval, manual refresh and fail-closed errors.
4. Full API/browser suites, build/format, independent review, contract and documentation.

No migrations or commits planned; preserve existing SAF-024 work.

Progress: initial 8 API tests failed on the absent route, then passed against the implementation. Browser RED confirmed absent Generate button after restoring the stopped local API. Initial browser GREEN covered generation, source navigation and stale hiding after evidence change. Additional cases cover external-session changes, repeated focus, unavailable validation, document source versions, audit-only reads, and release/deadline changes.

Review findings: one important issue, a blackholed validation had no timeout and retained visible facts indefinitely. Add held-request RED test, then a 10-second fail-closed timeout; rerun full verification. No other important/critical findings.
Final: minor (deferred): after summaries are disabled and subsequently re-enabled, an existing disabled browser snapshot needs a full page reload/case remount to recover. Document the reload; no stale financial facts are shown in this state.

Final: fixed unbounded validation — held-request regression failed on missing alert, then passed with 10-second timeout and hidden facts. Final full suites: `uv run --offline pytest -q` → 239 passed in 78.05s; `npx playwright test` (apps/web) → 13 passed in 1.4m. Build, Ruff lint/format, Prettier and diff whitespace checks passed. No other important/critical review findings. API contract and operator/requirements documentation updated; screenshot inspected. SAF-025 complete locally for deterministic fallback; SAF-026 remains next. No migrations, commits or external publication.
