# Implemented scope: M1 / SAF-001–007, M2 / SAF-008–012, M3 / SAF-013–015

Source: ../docs/design/NIDHISETU-REQUIREMENTS-ARCHITECTURE-v2.md and ../docs/SAFER-IMPLEMENTATION-BACKLOG.md. Later branding is SAFER.

| User story | Acceptance delivered |
|---|---|
| Provisioned officer signs in | OIDC authorization code with PKCE; local issuer/subject membership; no self-registration |
| Officer manages drafts | Positive exact-decimal INR, bank/reference, obligation and coherent dates; save persists across reload |
| Institution views its register | Server-side scope for list, detail, obligations, audit, edits and submissions; foreign objects return 404 |
| Officer avoids lost edits | Required version precondition; stale update returns 412; row locking serializes conflicting commands |
| Officer submits metadata | Confirmation; idempotency key; immutable snapshot and audit commit atomically; submitted record cannot edit |
| Auditor reviews | Read-only role enforced at API and UI, limited to assigned institution |
| User recovers failures | Error responses avoid raw input; failed form retains values; reauthentication in another tab preserves entered data |

Constraints: synthetic data, local HTTP loopback, single institution membership, provisioned demo obligations with illustrative amounts. Submission means metadata snapshot only. No legal sufficiency or bank confirmation implied.

Nonfunctional acceptance for this slice: deterministic decimal handling, tenant authorization, CSRF + origin checks, 30-minute idle/8-hour absolute expiry, transactional history, reproducible migrations and automated tests. Production availability, latency and recovery SLOs from v2 remain targets pending representative load and restore testing. No measured production SLA is claimed.

## SAF-008 — quarantined document upload

| User story | Acceptance delivered |
|---|---|
| Officer attaches supporting files to a draft | PDF/JPEG/PNG only; content signature must match declared type; ≤10 MB, PDFs 1–30 pages and unencrypted, images ≤40 megapixels; checks run in a time/CPU-limited child process with no environment credentials |
| Stored bytes are private and immutable | Private versioned S3-compatible bucket (SeaweedFS locally); server-side SHA-256 verification; record bound to exact object version + hash; a later overwrite never inherits that binding |
| Interrupted uploads are recoverable | Pending metadata commits before storage; failures mark the record failed; `python -m safer.documents` reconciles stale pending records and deletes unbound object versions |
| Scope and history | Institution/role scope, CSRF/Origin, 404 for foreign records, auditor read-only, drafts only, 20 active documents per record; success audited with document id, hash and version; database trigger forbids rebinding or deleting |


## SAF-009 — isolated scanning and audited download

| User story | Acceptance delivered |
|---|---|
| Untrusted bytes are scanned away from secrets | ClamAV 1.5.3 `scanner` container on an internal Docker network: no internet, no route to storage or database, no credentials. Signatures arrive through a separate `signatures` container that never receives files; the host reaches clamd only through a loopback TCP relay |
| Results apply only to the scanned bytes | The trusted worker fetches the exact object version, re-hashes it and records an append-only result with version + SHA-256. A hash mismatch is terminal (rejected); a clean result for any other version or hash is ignored |
| Failures stay quarantined | Scanner/storage errors retry up to 3 times, then the file shows Scan failed and stays blocked; infected and rejected files are never downloadable |
| Authorized, audited download | Institution-scoped (auditors may read), clean files only, bytes re-verified against the hash before release, audit written before the response, attachment-only with `CSP: sandbox` and no-store |

No in-portal preview exists, so no unsafe rendering path exists; an isolated-origin preview is deferred.

## SAF-010 — required documents before submission

| User story | Acceptance delivered |
|---|---|
| Requirements are configured, not hard-coded | Each obligation lists required kinds (`fdr_certificate`, `bank_letter`); new obligations default to an FDR certificate; database constraint limits values; `/obligations` publishes them |
| Submission needs clean evidence | Under the instrument row lock, every required kind's current upload must be scanned clean; otherwise 409 `documents_required` naming what is missing, with no state change or audit |
| Corrections keep history | The latest non-failed upload of a kind is current; earlier ones stay listed as replaced, with scan results intact. `other` files never satisfy a requirement |
| Submitted references are immutable | The submission snapshot records id, kind, filename, SHA-256 and object version of each required document plus clean `other` files; snapshots and documents are protected by triggers |
| Form guides the user | Checklist per requirement, type picker defaulting to the first missing kind, Submit disabled with the missing list until satisfied |

Corrections after submission (return-for-correction) belong with the review workflow, SAF-011.

## SAF-011 — review queue and independent evidence

| User story | Acceptance delivered |
|---|---|
| Reviewer works an assigned portfolio | `reviewer` role; `review_assignments` maps reviewers to institutions; queue lists only submitted cases of assigned institutions, oldest first; any other case, drafts included, is 404; removing an assignment revokes access immediately |
| Claims stay separate from evidence | Claims come from the immutable submission snapshot; evidence records hold field, bank-confirmed value, source, method (bank portal, bank email, letter from bank, call-back), observer and observation time, plus note; "uploaded document" is not an accepted method |
| Code decides match/mismatch | Exact rules per field (decimal amount, ISO date, exact reference, whitespace/case-insensitive bank name) against the latest evidence; history kept |
| Discrepancies and responses preserved | Reviewers raise observations (field or general); institution users respond; only reviewers resolve, once (row lock + unique index); replies after resolution refused; all rows append-only |
| Scope everywhere | Institutions and auditors see observations for their own records; assigned reviewers download clean case documents; every action audited into the institution's case history |

Reviewer assignment is seeded; managing assignments and delegation is SAF-017. Institutions cannot attach corrected documents to a submitted case yet; that needs a return-for-correction transition (SAF-019 workflow).

## SAF-012 — labelled bank simulator

| User story | Acceptance delivered |
|---|---|
| Reviewer can demonstrate bank confirmation without real access | "Request simulated confirmation" on a case; panel, evidence source, method and every result are labelled SIMULATED; no network call is made |
| Provider interface | `bank.PROVIDERS` maps a provider name to `provider(request, snapshot, key) -> signed answer` or `TimeoutError`; the simulator is the only entry |
| Binding | Each request records submission id and case row version before the provider is called; the answer must carry a valid HMAC signature, this request's id and provider, the same FDR reference and an observation time inside the request window |
| Replay / stale / timeout / tamper | One answer per request (unique + 409); answer for a changed case version → stale; timeout → no evidence; altered or replayed answers → rejected; all outcomes stored append-only with the raw answer |
| Never counts as confirmation | Simulator evidence uses method `bank_simulator`; the queue's "confirmed" count excludes it and shows a separate simulated count |

Scenario suffixes on the FDR reference: -MISMATCH, -NOTFOUND, -TIMEOUT, -TAMPER, -REPLAY. A real adapter (SAF-036) needs written authorisation, the bank's own authentication scheme and a hard network timeout.

## SAF-013 — durable background jobs

| Requirement | Delivered |
|---|---|
| Transactional outbox | `jobs.enqueue` inserts in the caller's transaction (rolls back with it); uploads enqueue their scan with the quarantine binding |
| Durable attempts | `jobs` holds state (queued/running/succeeded/dead, attempts, lease, last error); `job_attempts` is append-only per attempt |
| Redis/Celery delivery | Relay publishes job ids to Celery on Valkey 8.1; one task `safer.run_job`; JSON-only serialization, payload validated per kind, nothing unpickled |
| Bounded retries | Exponential backoff 30 s → 15 min cap; dead after max attempts; handler crashes are recorded, never lost |
| Deduplication | Unique dedup key per job; atomic claim makes duplicate or late deliveries no-ops |
| Stalled-job reconciliation | Running jobs past their 5-minute lease are requeued or ended, with a `stalled` attempt record |
| Broker-loss recovery | Unclaimed jobs are republished after 1 minute; queue holds no state (`--save ""`) |

Delivery is at-least-once; handlers must be idempotent (the scan handler is). All job times use the database clock.

## SAF-014 — maturity monitoring and reminders (FR04)

| Requirement | Delivered |
|---|---|
| Separate dates | FDR maturity, renewal action date (maturity − lead days) and obligation `required_until` (null = until released) are distinct; no action or escalation when cover ends before maturity |
| Versioned schedule | Immutable `reminder_schedules` (offsets, action lead, escalation delay, effective from); the latest version in effect applies forward; each reminder records the version it was generated under |
| Due work within 15 minutes | The relay sweeps every 60 s; each reminder records its due time, generation time and a `late` flag if generated more than 15 minutes after due |
| Test clock and catch-up | `deadlines.sweep(db, now)` takes an injectable clock; a sweep generates everything due and unrecorded, so missed runs catch up; unique (instrument, step) prevents duplicates |
| Escalation ownership | Escalations are owned by the institution's assigned reviewers, listed on the record; an unowned escalation shows "no reviewer assigned"; the queue flags escalated cases |

Notices whose time passed before submission are skipped; overdue actions and escalations are not. Escalation currently fires whenever the action date has passed because renewal/replacement linking arrives in SAF-016. Delivery of notifications (in-app, email) is SAF-015. The default schedule (90/60/30/7 days, 30-day lead, 7-day escalation) is illustrative and needs policy-owner validation.

## SAF-015 — notifications

| Requirement | Delivered |
|---|---|
| In-app notification | Each generated reminder notifies its recipients; bell with unread count, private inbox, per-user read state (CSRF-protected) |
| Local email capture | Email jobs (outbox) deliver to Mailpit on loopback; Message-ID is the notification id |
| Recipient scope | Institution steps → active institution officers of that institution (not auditors); escalations → active assigned reviewers; nobody else |
| Visible failed/uncertain | Per-recipient delivery state on each reminder: sent, failed (after retries or permanent refusal) or uncertain (connection lost during send, not retried) |
| Separate real-provider authorisation | `email_mode` accepts only `capture` and SMTP must be loopback; enabling a real provider needs a reviewed code and configuration change |
| No exactly-once claim | Documented: at-least-once jobs; uncertain sends are surfaced rather than retried |

Observation and review events do not notify yet; only reminders do.
