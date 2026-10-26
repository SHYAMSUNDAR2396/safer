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

## Recorded results — SAF-014, 23 October 2026

- API suite: **126 passed** (10 new): drafts get no reminders; a reminder fires at its due time and not one minute before; missed runs catch up four steps with no duplicates on rerun; 14 minutes late is on target, 16 is flagged; pre-submission notices skipped while overdue action and escalation fire; escalation owned by the assigned reviewer, visible as unowned after unassignment; a new schedule version applies forward and keeps history; no renewal steps when cover ends before maturity; the three dates stay separate in institution and reviewer views; reminders and schedules immutable.
- Corrected two of my own expectations: an FDR submitted 10 days before maturity is 13 days past its escalation point, so escalating at once is right.
- Audit trail now names system actors by source ("SAFER scheduler", "SAFER malware scanner").
- Playwright: **7 passed**; the new scenario submits an FDR maturing in 10 days, waits for the real relay sweep, sees the separate dates, overdue action and escalation with its owner, and the reviewer queue's Escalated flag.
- Environment: Colima had stopped (machine restart); restarted it and the Compose stack with volumes intact.

## Recorded results — SAF-015, 23 October 2026

- API suite: **134 passed** (8 new): recipients limited to institution officers and assigned reviewers (beta, auditor excluded); inactive and unassigned people get nothing; private inbox with per-user read state and CSRF; real Mailpit capture with notification-id Message-ID; unreachable SMTP retried then shown failed; connection lost during DATA shown uncertain and not resent; non-capture mode and non-loopback SMTP rejected by settings; notification content immutable.
- Fixed my own test ordering: deactivating alpha before creating the record made the create fail; the record is now submitted first.
- Playwright: **7 passed**; the deadline scenario now waits for real email jobs to report "sent", opens the bell inbox, marks the notification read, and checks the reviewer's escalation notification.

## Recorded results — SAF-016, 23 October 2026

- API suite: **149 passed** (15 new): proposed successor reported apart from counted cover; foreign, self, draft, partial, earlier-maturing and other-obligation successors refused with no row; one live proposal per side; cycle detection; acceptance moves cover with no double counting and is decided once; rejection restores both and allows a new proposal; only assigned reviewers decide; concurrent decisions → one 200, one 409; a proposal settles the renewal action (no action-due/escalation); link history immutable.
- UI review found two problems, both fixed: the coverage list showed every FDR on the obligation (page 4,700 px tall on demo data), now the record's chain with the full list in a native disclosure; and the deadlines panel gave the wrong reason when a replacement settled the renewal.
- Playwright: **8 passed**; new scenario: propose → reviewer accepts → old FDR shown Replaced, new Counts as cover, renewal shown settled.

## Recorded results — SAF-017, 23 October 2026

- API suite: **166 passed** (17 new): review grant takes effect immediately; release grant pending until a different admin approves (requester and grantee refused, second approval 409); database rejects self-approved activation; self-grant, admin grantee, institution user and auditor grantees refused; no authority over own organisation; only admins manage grants; duplicate live grant 409; expired grants confer nothing and do not block re-granting; revocation immediate and cascades to delegations; delegation cannot target self or non-reviewers or outlive its source; no re-delegation; delegated release authority pending; grant history immutable. All earlier scope tests now revoke grants instead of deleting assignments.
- Playwright: **9 passed**; new scenario: admin1 requests release authority (pending, cannot self-approve), grants review (active), admin2 approves, reviewer2 sees Alpha's queue, revocation empties it. Made repeatable against persistent demo data after the first rerun collided with leftover grants.

## Recorded results — SAF-018, 23 October 2026

- API suite: **179 passed** (13 new): second-admin publication (self-publish 403, republish 409); strict rules schema (empty, unknown, duplicate clearance, bad timing value, extra field → 422); only admins draft; versions resolve by effective date; drafts never apply; kind-specific beats general; `effective_until` ends a version; institutions read only their own applicable policy; snapshot shape and frozen published rows.
- Playwright: **10 passed**; new scenario: admin1 drafts, cannot publish; admin2 publishes; row shows "not validated by the policy owner". Found and fixed: policy rows did not display their note; the access test's wait matched policy rows before grants loaded.

## Recorded results — SAF-019, 23 October 2026

- API suite: **191 passed** (12 new): eligibility and policy required; one live request; clearance roles, schema and uniqueness; approval blocked by pending clearances, contradicting evidence and open observations; stale basis 412, idempotent replay, second key 409, no authority 404; clearer cannot decide (403 separation_of_duties); hold/resume/return/resubmit with decisions refused while held or returned; withdraw and re-request; concurrent decisions one 200/one 409; material change invalidates approval until reopened and re-decided; reopening a valid approval refused; release history append-only and transitions guarded.
- Playwright: **11 passed**; new end-to-end story: replacement accepted → release requested → two clearances by the reviewer → reviewer2 (release authority, dual-approved by two admins) approves → institution sees Approved. Found and fixed: the decision queue listed decided requests; decided cards showed an action input; clearance events showed raw codes; ready requests now say "Ready for decision".

## Recorded results — SAF-020, 24 October 2026

- API suite: **198 passed** (7 new): instruction needs a valid approval and release authority, once only; invalidated approval cannot be instructed; execution needs an instruction, separation from approver/instructor, strict evidence schema; difference blocks closure and the latest evidence governs; approval alone cannot close; closure marks the FDR closed, it leaves the queue but stays readable, and further evidence is refused; no payment-like API paths; instruction/execution history append-only.
- Found by the browser story and fixed: the institution register returned 500 once an FDR was closed (view status did not allow `closed`; regression test fails without the fix); closed records hid their release history; closed cases still offered live reviewer actions.
- Playwright: **11 passed**; the release story now runs request → clearances → approval → instruction → execution evidence → matched reconciliation → closure, seen by all three roles.

## Recorded results — SAF-021, 24 October 2026

- API suite: **205 passed** (7 new): lifecycle buckets reconcile to a known fixture and to the register summary; attention metrics follow their definitions before and after a sweep; a proposed replacement removes an FDR from renewal-action-due; every metric's drill-down has exactly its count and amount; unknown metric 404; scope by institution and authority (reviewer sees Alpha only, no drafts; revoked grants see nothing; beta sees only Beta); per-obligation cover; release work queues move through clearing, ready and awaiting instruction.
- Playwright: **12 passed**; new scenario: a tile's count equals its drill-down rows and opening a row opens that record; reviewer sees release work and no drafts. Screenshot reviewed: flagged tiles use icon plus label, meter separates proposed from counted cover.

## Recorded results — SAF-022, 24 October 2026

- API suite: **214 passed** (9 new): asynchronous build matching the dashboard drill-down, attachment CSV and audit trail; formula-prefixed cells neutralised (stored data unchanged); grant revoked before the job runs → failed with nothing stored; grant revoked after build → download 403; expiry → 410 and purge deletes all stored versions; owner-only access (beta and auditor 404, beta's export excludes Alpha); only visible metrics (unknown 422, reviewer drafts 422, admins 403); duplicate delivery builds once; deactivated owner gets nothing.
- Playwright: **12 passed**; the dashboard scenario now exports a drill-down through the real relay and Celery worker and checks the downloaded CSV's row count equals the tile.

## Recorded results — SAF-023, 24 October 2026

- API suite: **222 passed** (8 new): positioned proposals from a real text-layer PDF; ambiguous and missing fields abstain; an impossible date abstains instead of guessing; images fall back to manual entry; unscanned documents are never parsed (409); access inherits the document (beta 404, auditor allowed, reviewer only on reviewable cases); proposals never change the claim or create evidence, and reviewers see a differing extracted value flagged; unreadable text layer fails safely.
- Playwright: **13 passed**; new scenario: a draft with a wrong amount, a real receipt upload, the clean scan and extraction jobs, proposals shown with page and source line, values applied through the edit form, and the amount changing only after Save. Screenshot review fixed field labels breaking onto separate lines.

## Recorded results — SAF-024 fallback, 24 October 2026

- Full API suite: **229 passed in 60.50s**, real dedicated PostgreSQL test database/object store/ClamAV. Seven new tests cover code-determined mismatch with exact citations, new-evidence basis changes, wrong-role/scope/revocation denial, independent disable with manual comparison retained, simulated evidence boundaries, frozen document version/hash/run/page provenance and instruction-like evidence notes treated only as data. Initial RED: seven missing-route failures.
- Playwright: **13 passed (1.3m)** against the real local API, Keycloak and jobs. Extended the reviewer workflow to open explanations, inspect the mismatch, expand source versions and follow the evidence link to the exact log entry. Initial RED: no explanation UI. A later locator failure was corrected by opening the collapsed source disclosure before clicking its link. Full-page `apps/web/test-results/explanations.png` inspected.
- TypeScript + Vite build, Ruff checks/format (71 Python files), Prettier and `git diff --check`: pass. OpenAPI snapshot regenerated from the implemented application.
- Independent read-only review: no important findings. No production security/load test, model evaluation or remote AI/provider integration is claimed. This verifies the labelled deterministic fallback, not model-generated FR14 wording. Source cache is not persisted; a case refresh recomputes its basis. Deliberate no-model decision is recorded in SAF-024-PLAN.md.

## Recorded results — SAF-025 local summaries, 24 October 2026

- Final full API suite: **239 passed in 78.05s** against dedicated PostgreSQL/object storage/ClamAV. Ten summary tests cover exact financial strings and dates, stable material digest, evidence and observation invalidation, wrong roles/scope/revoked assignment, independent disable, simulator exclusion, instruction-like notes, malformed digest, frozen document citations and audit-only reads, release/monitoring changes. Initial RED: eight missing-route failures. Extended fixtures were corrected to require the certificate and use the existing hold endpoint's 200 response.
- Final real-Keycloak Playwright suite: **13 passed (1.4m)**. Reviewer workflow covers generation, source navigation, local evidence changes, an authenticated external-session change, persistent stale state across repeated focus/source refresh, explicit regeneration, unavailable validation and a held validation request. Original UI RED: absent Generate button; sticky-stale RED reproduced automatic restoration; review-finding RED reproduced missing timeout. All are green in the final run.
- Independent read-only review found one important issue: unbounded validation could retain visible facts on a hanging request. Fixed with a **10-second timeout**, cancellation and hidden facts; held-request test RED→GREEN and full suites green. No other important/critical findings. Deferred minor: browser reload needed after a disabled snapshot is re-enabled.
- TypeScript/Vite production build, Ruff lint and format (71 files), Prettier and `git diff --check`: passed. OpenAPI snapshot regenerated. Full-page reviewer screenshot inspected for readable summary cards and resolvable source disclosures.
- Local deterministic/advisory scope only: no model, external AI transfer, persisted summary history, production load/security certification or real bank integration is claimed. SAF-026 evaluation remains next.

## SAF-026–032 local readiness protocol

Use only the dedicated test DB/bucket for API tests, the original labelled synthetic
demo for workflow tests and the isolated readiness profile for HTTPS/encryption/drills.
Serialize DB test suites; do not run the evaluation security subprocess concurrently
with the full API suite. Browser commands must run from `apps/web`, because private
fixture paths are relative to that directory. The MFA helper may wait for a fresh
30-second TOTP counter; this exercises real replay prevention rather than disabling it.

```sh
uv run pytest -q
PYTHONPATH=apps/api uv run python -m safer.evaluation --security --output .local/evaluation/saf026-final
uv run ruff check apps/api scripts
uv run ruff format --check apps/api scripts
(cd apps/web && npm run build && npm run format:check)
(cd apps/web && npx playwright install chromium && npx playwright test)
(cd apps/web && npx playwright test --config playwright.readiness.config.ts)
PYTHONPATH=apps/api uv run python scripts/readiness_evidence.py
./scripts/security_scan.sh
```

Run the two browser suites sequentially: they share local Keycloak fixture identities.
Start the current API/relay/worker/frontend and readiness containers first; refresh
the one-hour Transit token as documented in DEPLOYMENT.md. Restore component and
capacity commands create new scratch databases and preserve them for inspection:

```sh
PYTHONPATH=apps/api uv run python -m safer.local_drills audit
PYTHONPATH=apps/api uv run python -m safer.local_drills recovery
PYTHONPATH=apps/api uv run python -m safer.capacity
```

Source-secret scanning is a separate invocation from the image/dependency/SBOM script.
It deliberately excludes generated/private files, dependency caches and Git metadata;
this is not proof that excluded private files contain no secrets. Do not publish raw
scanner matches. The locally executed command/evidence is:

```sh
docker run --rm -v "$PWD:/source:ro" aquasec/trivy:0.76.0 fs --scanners secret --exit-code 1 --skip-dirs /source/.git,/source/.venv,/source/.local,/source/apps/web/node_modules --skip-files /source/.env --format json /source > .local/saf031-source-scan.json
```

Hosted CI definitions include backend/browser/evaluation and separate security builds,
but hosted runs are not claimed. See PILOT-READINESS.md for independent-assessment,
provenance, rollback and representative-acceptance gaps.


## Recorded readiness results — 25 October 2026

- Final complete API suite: **272 passed in 76.63s** against dedicated PostgreSQL/object-store/scanner fixtures. Includes privileged session/role-promotion MFA boundaries, encryption context/tamper/legacy rejection, metric/evidence gates, safe restore names, redacted alerts and scoped queue pagination.
- Final complete workflow browser suite: **13 passed in 6.1m**, actual local Keycloak/TOTP, API, PostgreSQL, objects, relay and worker. Covers source-linked/stale summaries, simulated evidence boundaries, renewal, dual-control release through matched closure, dashboard/export and extraction. Accumulated >200-case inventory exercises Load more cases and secondary-session paginated lookup. Real TOTP replay prevention increases test time; MFA was not bypassed.
- Final separate HTTPS/readiness browser suite: **2 passed in 7.5s** on final container images: encrypted upload/scan/submission, Secure session cookie, privileged TOTP review/summary; automated axe/WCAG and keyboard register/dialog checks. Exact TLS trust-anchor, encrypted version/hash and DB permission checks separately passed. Automated checks are not full accessibility certification. Reviewer screenshots inspected for layout/source readability; no credential screens are published.
- Evaluation: **138 synthetic documents, 12 review cases, 26 independently collected/executed safety tests**, zero wrong proposals/parser/summary/citation errors and comparison precision/recall 1.0 on this corpus. Scans have manual fallback/zero extracted coverage. The corpus is regression data, not representative held-out acceptance. Latest measured timings/provenance are in evaluation/SAF-026-RESULTS.md and .local/evaluation/saf026-final.
- Python dependency audit: **0 known findings**, after Pillow13 security upgrade. Node audit: **0 findings at every severity**. Final API/web runtime scans: **0 HIGH/CRITICAL findings**; API/web CycloneDX SBOMs and image/archive correspondence recorded. Final source-secret scan: **0 findings in its declared scope**. Raw matches/private files are excluded from published artifacts. These describe the actual scanned versions/database at execution, not future vulnerability absence.
- TypeScript/Vite build, Ruff lint and format (**91 Python files**), Prettier and diff whitespace checks passed. OpenAPI regenerated, including reviewer cursor/limit parameters. Hosted CI was prepared, not run; no signed build attestation or independent security assessment is claimed.
- One independent read-only review found two important evaluation gaps (incomplete JUnit and misplaced section/release citations). Both had failing reproductions, fixes and a green complete suite. Later integration found/fixed the older queue truncation, with dedicated RED→GREEN scope/pagination regression and full API/browser passes. No second review was dispatched.
- After all browser runs, removed only explicitly labelled test-owned OTP factors on four fixed synthetic accounts and revoked their app/IdP sessions. Personal factors were preserved; required MFA remains. Next human privileged login enrolls its own authenticator. No real identity was reset.

Local component evidence also verifies six Mailpit-capture alert rules, encrypted DB dump/isolated restore, and the declared 1,000-request scoped workload (49.99 arrival / 49.94 completion RPS, p95 reads 30.601ms/writes 29.166ms). **Full DR, independent assessment/rollback and sponsor acceptance remain incomplete.** Read PILOT-READINESS.md for every gate and the two deferred minor improvements. No real/anonymized receipts, cloud provider APIs, publication or production activation.

## Optional LLM tests

Run `.venv/bin/pytest apps/api/tests/test_llm.py apps/api/tests/test_ai.py -q`, then the full `.venv/bin/pytest -q` suite. Apply migration 019 to the dedicated test database first. With Vite running, run `npx playwright test e2e/ai.spec.ts` from `apps/web`. These use simulated provider HTTP and real database/React behavior; they do not establish live model accuracy. The existing deterministic evaluation results remain separate. See [live evaluation gates](design/LLM-INTEGRATION.md).

26 October 2026 LLM integration evidence: full backend suite 311 passed (66.45s); full main browser suite 15 passed (5.0m); frontend build/format and backend lint/format passed. Independent review findings on malformed usage metadata and nested pool checkouts were reproduced and fixed. The main browser suite includes two AI component tests; external model quality remains untested and inference remains off.
