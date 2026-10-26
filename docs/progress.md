# First-slice progress — plan: ../../docs/superpowers/plans/2026-10-22-safer-first-slice.md

22 October 2026: user approved backlog creation and immediate first-slice implementation. Using writing-plans, executing-plans and test-driven-development.

Ruling: fresh `safer/` Git repository on feat/first-slice isolates application code from existing research/assets; no existing app to migrate. Parent is not a Git repository, so skill task helper scripts are replaced with this ledger.

Ruling: M1 submits synthetic metadata only, visibly labeled. Document submission prerequisites remain SAF-008–010; this is not a completed regulatory application. Production startup will be blocked.

Ruling: one provisioned local institution/role membership per user in M1. No self-enrollment, global admin or delegated financial permissions; richer authority remains SAF-017.

Pre-flight: auth produces user/session context consumed by instruments; instrument JSON schemas feed UI. Same-origin browser URL is localhost:5173 and identity issuer localhost:8090. Trusted identity subject is mapped locally, never from token-provided institution/role.

Completed: environment/migrations, real OIDC, tenant authorization, draft/edit/submission with atomic history, responsive frontend, test fixtures and repeatable seed, OpenAPI export, runbooks and CI definition.

Evidence: initial API missing-endpoint tests failed before implementation; initial browser scenarios failed at missing login before screens were built. Final results are 33 API tests and 4 browser scenarios passing. Type/build, Ruff and Prettier checks pass. Screenshot review found and fixed mobile scrolling overflow.

Independent reviewer found expired-session forms had no recovery. Added new-tab reauthentication with same-user/institution/role check and refreshed CSRF; revoked-session browser regression passes; reviewer confirmed resolution.

Architecture ruling: one-screen React local state/fetch avoids introducing a router/cache before required. API types are explicit manual TypeScript contracts; generated client remains future evolution. No financial decision, AI inference, document verification or bank integration is represented as implemented.

M1 verified locally. Hosted CI is prepared, not executed. Tests leave labeled synthetic records in local demo database. No production deployment or remote repository publication occurred.

## M2 / SAF-008 — 22 October 2026

User asked for secure FDR document upload (M2). Scoped to SAF-008; SAF-009 (scan sandbox, downloads), SAF-010 (mandatory documents) and later remain open.

Ruling: SeaweedFS 4.48 as local S3-compatible store (MinIO community images discontinued). Spike verified bucket versioning, version-exact reads, server-side SHA-256 rejection and anonymous denial before adoption.

Ruling: raw-body upload (not multipart) to avoid a new parser dependency and stream with a hard cap after authentication. Checks run in a credential-free child process; full sandboxing is SAF-009.

Evidence: 24 new API tests failed at import before implementation, then passed. A weak PNG fixture was being rejected as unreadable rather than for size; fixed and now asserted. Bootstrap mounted files were 0600, unreadable by non-root containers on Linux CI; now 0644 inside a 0700 directory.

## M2 / SAF-009 — 23 October 2026

User asked to continue with the next phase. Scoped to SAF-009.

Ruling: ClamAV `clamav/clamav-debian:1.5.3` (the default `clamav/clamav` tags have no arm64 build). clamd on an internal network with a socat relay, freshclam in a separate container. Spikes confirmed INSTREAM verdicts and that EICAR is detected only as a raw stream, so infected-file tests store raw EICAR directly.

Ruling: scan results are append-only rows; document state is derived so the document binding stays immutable. System audit events use a null actor shown as "SAFER malware scanner".

Ruling: no previews. Attachment-only download with sandbox CSP removes the unsafe rendering path; an isolated-origin preview is deferred until needed.

Evidence: 9 new tests failed at import, then passed. A double count of scan errors (autoflush) was caught in review before running. The first browser run failed because the earlier session's Vite server had stopped and the worker lacked PYTHONPATH; both corrected and documented.

## M2 / SAF-010 — 23 October 2026

Ruling: requirements live on the obligation as a constrained array; a requirements table can come with policy versioning (SAF-018). Default is an FDR certificate; demo obligations got the default from the migration.

Ruling: "current" document per kind is derived from upload order rather than an explicit supersede action: the institution's latest file is its claim, and nothing is deleted.

Evidence: 8 new tests failed before implementation, then passed. One older test built a document without a kind and was updated. One browser locator became ambiguous with the new checklist text and was made exact.

## M2 / SAF-011 — 23 October 2026

Ruling: reviewer scope is an assignment table (portfolio by institution); the reviewer's home organisation is a demo "AICTE Regulation Bureau" row in institutions, which owns no records. Per-case assignment and delegation wait for SAF-017.

Ruling: evidence is append-only per field; the latest record is compared, earlier ones remain. Match/mismatch is deterministic code, aligned with "no AI or uploaded claim becomes independent bank confirmation".

Ruling: Keycloak imports its realm only once, so `scripts/sync_identity.py` adds new demo users through the admin partial-import API, preserving fixed subject ids.

Refactor: shared UI helpers moved to `ui.tsx`; reviewer screens in `Review.tsx`.

## M2 / SAF-012 — 23 October 2026

Ruling: provider "interface" is a dict of functions with a documented contract, not a class hierarchy; the simulator is the only entry until an authorised adapter exists.

Ruling: simulated evidence is real data in the evidence table (so comparison logic is exercised) but is distinguished by method and excluded from confirmation counts everywhere.

M2 (SAF-008–012) is complete locally.

## M3 / SAF-013 — 23 October 2026

User asked to continue phase by phase without confirmation. Committed M1–M2 as a checkpoint (7183fcf) first.

Ruling: database-as-ledger outbox with Celery as transport (backlog names Redis/Celery); Valkey 8.1 instead of Redis for licensing. One generic task runs any job id; per-kind payload schemas.

## M3 / SAF-014 — 23 October 2026

Ruling: the sweep runs inside the relay loop rather than as Celery beat, keeping one scheduler and the database clock. Reminders are records (the "due work"); delivering them as notifications is SAF-015.

Ruling: due time is 09:30 IST on the computed day.

## M3 / SAF-015 — 23 October 2026

Ruling: Mailpit v1.31.3 captures email locally. Handlers now receive `final` on their last attempt so a permanently undeliverable email ends as visibly failed rather than stuck pending.

## M3 / SAF-016 — 23 October 2026

Ruling: coverage counts submitted claims (labelled as such) because accepted-evidence coverage depends on the release lifecycle (M4). A proposal, not only an acceptance, settles the institution's renewal action; the reviewer's decision is then the open item.

M3 (SAF-013–016) complete locally.

## M4 / SAF-017 — 23 October 2026

Ruling: grants replace review assignments (migrated), because expiry, revocation, delegation and dual control are properties of authority, not of a role column. Admins are a separate role that never holds case authority.

## M4 / SAF-018 — 23 October 2026

Ruling: one policy code (`release`) with a strict rules schema rather than a generic rules engine; new codes get their own schema when a decision needs them.

## M4 / SAF-019 — 23 October 2026

Ruling: "competent decision" = active release authority plus separation from clearance work. "Material change" is a deterministic fingerprint rather than a list of watched events, so new material inputs only need adding to `basis()`.

## M4 / SAF-020 — 24 October 2026

Ruling: instruction is a record with a reference; delivery to the bank and actual execution are outside SAFER. Reconciliation compares amounts only; date and beneficiary checks would need real bank data formats.

M4 (SAF-017–020) complete locally.

## M5 / SAF-021 — 24 October 2026

Ruling: metrics are declared once as SQL conditions; the total and the drill-down run the same query. The dashboard replaced the older ad hoc stat tiles on the register and review queue. Dataviz skill guidance applied (stat tiles, meter, reserved status colour with icon and label, table view).

## M5 / SAF-022 — 24 October 2026

Ruling: no signed URLs; downloads always pass through the API so re-authorisation is real. Export scope is fixed at build and must still hold at download.

## M5 / SAF-023 — 24 October 2026

Ruling: deterministic text-first extraction instead of an AI model: the backlog asks for text-first extraction with abstention, which fixed rules meet without sending data to a provider. OCR stays unconfigured; scanned images need manual entry. Applying values reuses the normal edit form, so acceptance is the officer's save.

Also: design-hook review replaced thick coloured side stripes on cards with tinted outlines (every card already carries a text status).

## SAF-024 fallback — 24 October 2026

Ruling: local deterministic templates, not generated AI wording, until a provider/privacy choice is made. This preserves the manual fallback without pretending that an AI model exists. No outbound data transfer or authoritative writes. Exact evidence IDs and frozen document version/hash/run/page citations, per-request basis digest, scoped reviewer access and independent switch-off. Provider-generated FR14 wording remains deferred.

API RED: 7 missing-route failures; GREEN: 7 targeted and 229 full-suite passes. Browser RED: explanation UI absent; source-link check subsequently corrected to expand the native Sources and versions disclosure before clicking. Independent read-only review found no important findings. Build and backend/frontend lint/format pass. Browser final results are recorded in TESTING.md after the suite completes.

Final browser result: **13 passed (1.3m)** including the expanded source-linked mismatch workflow; screenshot inspected. SAF-024 local fallback verified, provider-generated explanations remain pending. No production deployment or external provider access.

User decision (24 October): explicitly chose local fallback for SAF-024. Approved fallback scope is complete and verified; no AI provider selection is pending for SAF-024. Model-generated wording remains an optional future enhancement. No code or runtime changes were needed.

## SAF-025 local case summaries — 24 October 2026

Implemented versioned deterministic summaries over the current authorized reviewer case view, with exact immutable submission facts, latest-evidence counts excluding simulations, frozen document citations, observation/deadline/release source links, independent disable, and an explicit material-basis digest. The browser hides changed facts until regeneration and hides facts on failed or timed-out validation (15-second polling/focus, 10-second timeout). No model, external transfer, schema migration or stored summary history.

Verification: **239 API tests in 78.05s; 13 real-login browser tests in 1.4m; frontend build; Ruff lint/format; Prettier; diff whitespace check**. Independent review's unbounded-validation issue fixed with held-request RED→GREEN; no other important findings. Deferred minor: reload after summaries are re-enabled. Local SAF-025 scope complete. SAF-026 evaluation is next; pilot gates remain unverified. No commits, remote publication or production deployment.


## SAF-026–032 local readiness — 25 October 2026

User approved synthetic-only, provider-neutral local work: portable containers; Keycloak privileged TOTP; OpenBao Transit behind a key wrapper; future India-resident hosting; no provider APIs or real/anonymized receipts without written data-owner approval.

Implemented 138-document/12-review synthetic regression evaluation with independent labels, exact denominators/abstention, source/library/corpus provenance and 26 executed security-test identities. Initial two unsafe amount proposals fixed test-first; observed corpus became regression data. Representative holdout/utility acceptance remains blocked.

Added portable non-root/read-only HTTPS API/web/worker containers, separate synthetic DB/bucket/queue, restricted runtime/migration roles, context-bound encrypted object envelopes and private runtime/operator mounts outside checkout/.env. Keycloak privileged TOTP/LoA2 and per-request MFA session assurance require migration018. Federation stays disabled configuration; real hosting/keys/identity acceptance remains pending.

Actual local evidence: Transit context/admin-denial checks; exact TLS trust-anchor verification; encrypted-version hash roundtrips; runtime DDL/immutable-update/delete denials; encrypted audit projection/checkpoint integrity and six Mailpit-capture alert rules; encrypted dump/restore into NEW isolated scratch DB; 10k/100k seeded scoped ASGI workload at49.99 arrival / 49.94 completion RPS, read p95 30.601ms/write p95 29.166ms, no unexpected/server errors. DR is a database component only, not full PITR/object/identity/key-loss recovery or RPO/RTO proof.

One independent read-only review found two important evaluation flaws: partial security JUnit could pass; summary citations could move to another section. Both reproduced RED and fixed GREEN; missing/duplicate/skipped test identities and wrong section/release sources now fail. A later real browser run exposed the older 200-case queue truncation; bounded keyset pagination and Load more cases now preserve access beyond the first page with reauthorized anchors. Regression RED→GREEN; final API suite272 passed in 76.63s. Final browser/container/readiness results are recorded in TESTING.md after their runs complete.

Final dependency audits report zero known Python and Node findings; final runtime scans report zero HIGH/CRITICAL, with SBOMs and matched archive/image evidence. Source secret scan reports zero findings in its declared scope. These are time/artifact-specific local results. Full independent security assessment, hosted CI, signed provenance, rollback rehearsal, broader accessibility acceptance and real operational control verification remain pending. No commit, publication, production activation or real data use.

Read docs/PILOT-READINESS.md and docs/DEPLOYMENT.md for evidence, one-hour key-token refresh, MFA fixture cleanup and all blocked sponsor/platform gates. SAF-029/031/032 remain incomplete as full pilot requirements. Local readiness does not remove production-mode rejection.

Final readiness verification:13 workflow browser tests passed in 6.1m;2 HTTPS/encryption/accessibility browser tests passed in 7.5s. Updated foundation evidence passed after the final upload; labelled synthetic test OTP factors cleaned up on 4 fixture identities, preserving personal factors and required MFA. All 7 real-data pilot statuses remain blocked in .local/pilot-readiness.json. No further code changes after final green suites; evidence/docs only.
