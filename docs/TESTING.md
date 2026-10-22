# Verification

Run commands in README. API suite uses real PostgreSQL, not SQLite or mocked persistence. Fixtures truncate only the dedicated safer_test database; migrations must be applied first. Session fixtures bypass browser login only inside tests. No test-login endpoint exists in application.

Coverage: unauthenticated access, session expiry/revocation, CSRF/origin, auditor writes, tenant boundaries on all object operations, invalid amounts/dates/text/extra fields, persistence with a fresh engine, stale updates, immutable submitted records, idempotent replay, concurrent conflicting submissions, audit-write failure rollback, database history mutation guards and repeatable seed.

Playwright uses real local Keycloak. Covers create/edit/submit/reload/audit, separate institution and auditor roles, mobile layout, storage-failure input preservation and session recovery with retained input. Browser records remain in synthetic demo DB; APIs use separate test DB.

`npm run build` runs strict TypeScript plus Vite production compilation. Python formatting/lint use Ruff. Source tests and browser screenshots provide evidence; no performance benchmark, accessibility audit, container vulnerability audit or production penetration test has been completed.

CI workflow repeats build, lint, migrations, API tests and browser tests using ephemeral CI services. Workflow is prepared but its hosted execution is not claimed until an actual run occurs.

## Recorded results — 22 October 2026

- PostgreSQL API suite: **33 passed in 2.20 seconds** on final backend source.
- Playwright Chromium: **4 passed in 4.9 seconds**, real Keycloak and local API; includes session recovery.
- Strict TypeScript + Vite build: passed after frontend formatting.
- Ruff: all checks passed, 20 files formatted. Prettier check: passed.
- Desktop submitted-record and 390px mobile-form screenshots inspected; mobile overflow fixed by positioning the scrolling table container.
- Independent static review found one important session-expiry recovery issue; fixed and re-reviewed with no remaining important findings. This is not a penetration test.
- npm installation audit reported zero vulnerabilities; this does not cover Python/containers or substitute for ongoing scanning.
- Hosted CI, load testing and disaster-recovery exercises remain unexecuted.

## Recorded results — SAF-008, 22 October 2026

- PostgreSQL + object-store API suite: **57 passed** (33 existing + 24 document tests): accepted PDF/PNG/JPEG bound to exact version and hash; scope/auditor/CSRF; 12 rejection cases (signature, type mismatch, empty, >10 MB, 31 pages, encrypted, corrupt PDF, decompression-bomb and 49 MP PNG, truncated JPEG, bad names) leaving no row, object or audit; submitted-record lock; per-record cap; storage outage → failed without audit; overwrite cannot inherit binding and reconciliation removes it; stale pending reconciliation; trigger blocks rebinding/deletion.
- Test bucket `safer-documents-test` is emptied per test; the guard refuses other buckets.
- Playwright: **4 passed** against real Keycloak/API/object store; the main scenario now uploads a PDF, sees Quarantined + audit entry, gets a rejection for a renamed text file, and confirms upload is gone after submission.
- Alembic 003 downgrade/upgrade round trip on safer_test; Ruff, Prettier and strict TypeScript build pass.
- Not covered: malware scanning, network isolation of the checker (macOS does not enforce the memory limit), load on uploads, restore of object data.

## Recorded results — SAF-009, 23 October 2026

- API suite with real PostgreSQL, object store and ClamAV: **66 passed** (9 new): clean upload → scan → download with exact bytes, attachment/CSP/no-store headers and audit order; EICAR detected and permanently blocked; hash-mismatch bytes rejected without scanning; scanner outage retried 3 times then failed with one audit event; forged clean result for another version ignored; key overwrite after scanning still serves the scanned version; tampered bytes refused at download without audit; beta 404, auditor allowed; scan history immutable.
- Isolation probe: from the `scanner` container, internet (1.1.1.1:443), `objects:8333` and `db:5432` are unreachable and no credential variables exist; the host reaches clamd only via 127.0.0.1:3310. Added to CI.
- Playwright: **4 passed**; the main scenario waits for Scanned clean, downloads the file and compares it byte for byte with the uploaded PDF.
- Alembic 004 downgrade/upgrade round trip; Ruff, Prettier and strict TypeScript build pass.
- Not covered: real malware beyond EICAR, scanner throughput, signature-update failure alerts, previews (none exist).

## Recorded results — SAF-010, 23 October 2026

- API suite: **74 passed** (8 new): default requirement; submission blocked until required kinds are uploaded and clean (pending scans do not count); refused attempts change nothing; infected certificate replaced by a corrected upload, history kept and only the correction referenced; newest upload of a kind governs; `other` never satisfies; unknown kind 422; obligations publish requirements; idempotent replay intact.
- M1 metadata tests use an obligation explicitly configured with no required documents.
- Playwright: **4 passed**; the main scenario checks Submit is disabled with "FDR certificate" listed, uploads, waits for a clean scan, then submits. Draft screenshot reviewed.
- Alembic 005 downgrade/upgrade round trip; Ruff, Prettier and TypeScript build pass.

## Recorded results — SAF-011, 23 October 2026

- API suite: **91 passed** (17 new): queue scope (assigned, submitted only; drafts/foreign 404; institution/auditor 403; reviewer cannot create records); claim vs evidence comparison and retained source/method/observer/time; 9 invalid-evidence cases leave no row; typed date/reference validation; assignment removal revokes access; full observation thread with role rules, single resolution and late-reply refusal; concurrent resolution → one 201, one 409; review tables immutable; assigned reviewer downloads clean documents, loses access when unassigned.
- Found and fixed: the test fixture never disposed per-client connection pools, exhausting PostgreSQL's 100 connections once the suite grew (order-dependent failures). Clients now dispose their engine.
- Playwright: **5 passed**; the new scenario runs alpha submit → reviewer evidence (Match/Mismatch) and observation → alpha response → reviewer resolution across real Keycloak logins. The comparison table was clipped in the first screenshot and was fixed.
- Alembic 006 downgrade/upgrade round trip; Ruff, Prettier and TypeScript build pass.

## Recorded results — SAF-012, 23 October 2026

- API suite: **103 passed** (11 new + 1 regression): signed, bound, labelled simulated confirmation; not found / timeout / tampered / replayed answers leave fields unconfirmed; simulated mismatch detected by code; answer for a changed case version → stale; the same answer accepted twice → 409; post-signature value change rejected; scope (institution 403, unassigned 404); bank tables immutable.
- Bug found by the stale test: a locked re-read returned the session's cached instrument, so version and status changes made after a commit went unseen. Fixed in `scoped_instrument` and bank acceptance. New regression test submits the record while an upload is being stored; it fails without the fix and passes with it.
- Playwright: **6 passed**; the new scenario requests a simulated answer for a -MISMATCH reference, sees "Mismatch · simulated"/"Match · simulated", and the queue still shows 0 of 5 confirmed.
- Alembic 007 round trip on an empty test database; Ruff, Prettier and TypeScript build pass.

## Recorded results — SAF-013, 23 October 2026

- API suite: **116 passed** (13 new): upload enqueues exactly one deduplicated scan job; enqueue rolls back with its transaction; relay publishes once, republishes after simulated broker loss, leaves jobs on publish failure; execution claims once and skips duplicate delivery; retries back off and end dead at the limit; not-yet-due jobs neither publish nor run; unknown kind / invalid / extra-field payloads end dead without executing; stalled jobs are reclaimed; attempt history is append-only; real Valkey + Celery worker delivers a scan end to end.
- Found and fixed: a developer's Homebrew Redis already listened on 127.0.0.1:6379, so the broker moved to 56379. The host and Docker clocks differ slightly, so job times now use the database clock (this caused a requeued job to look not yet due).
- Live checks on the demo stack: Celery's prefork pool crashed on macOS/Python 3.14; its three jobs were republished and succeeded once the worker ran with threads. With the queue stopped, the relay stayed up and the job stayed unpublished; after restart it was published and succeeded on attempt 1.
- Playwright: **6 passed** with scanning now driven by jobs.
