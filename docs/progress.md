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
