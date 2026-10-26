# SAFER local readiness and pilot gates

Updated 25 October 2026 (measurements began 24 October). **Synthetic data only. Every real-data pilot gate remains blocked.**
This report separates implemented local controls from evidence that requires AICTE,
an independent assessor or the selected hosting platform. `APP_MODE` still accepts
only `local`. The gate ledger is a planning record, not an attestation or activation API.

## Decisions and assumptions

The user approved portable Docker/Compose packaging, Keycloak with privileged TOTP,
an OpenBao Transit adapter, and synthetic-only evaluation. No hosting provider,
external identity provider, KMS/HSM or real/anonymized FDR dataset is selected.
Any real or anonymized FDR needs **written approval from AICTE's data owner first**.
The future target is a MeitY-empanelled Indian cloud or NIC/MeghRaj; application,
replicas, backups, logs and key services must remain in India. No cloud provisioning
or provider-specific API calls were made. Registry/package/security-metadata downloads
are development dependencies, not a deployment to a provider.

The changeable assumptions are recorded in `infra/pilot/assumptions.json`. Retention,
legal holds, policy/authority matrix, real responders and contractual responsibilities
are explicitly undecided. Optional WebAuthn and external federation need their own
enrollment, claim-assurance, revocation and recovery tests before use.

## Phase evidence and remaining gates

| Phase | Implemented and measured locally | Evidence still required for pilot |
|---|---|---|
| SAF-026 | Offline evaluation: 138 synthetic documents, 12 review cases; zero wrong proposals, 264 exact summary facts and 69 source citations checked; 26 API safety regressions | Approved representative holdout, accuracy/utility thresholds and human baseline |
| SAF-027 | HTTPS front door, privileged Keycloak TOTP/LoA2, session assurance, context-bound AES-256-GCM envelopes, restricted DB runtime role, non-root/read-only API/web containers | Hosting/residency, public certificate chain, encrypted internal links/volumes, separate worker/storage permissions, parser filesystem/credential/egress isolation, independent key custody/workload identity |
| SAF-028 | Encrypted minimal audit projection, separate checkpoint integrity checks, six redacted alert rules delivered to local Mailpit capture | Independent immutable destination, retention/holds, real SIEM connectors and named responders |
| SAF-029 | Actual encrypted PostgreSQL backup, decrypt and restore into a new scratch DB; 30 table counts/41 rows reconciled in the recorded fixture | PITR, exact object-version restore, identity/key-loss recovery, independent administrator, whole-system RPO/RTO and incident tabletop |
| SAF-030 | 10k institutions/100k initial FDRs; 1,000 scoped API requests, 800 reads/200 writes; 49.99 arrival RPS/49.94 completion RPS; p95 read 30.601ms/write 29.166ms; zero unexpected/server errors | Full-portfolio and transport workload, file/queue/login performance, quotas and upstream DDoS/origin controls |
| SAF-031 | Dependency/image/source checks, SBOMs, browser/keyboard/automated accessibility checks, independent code review and regression fixes | Independent security assessment, hosted CI, signed provenance, rollback rehearsal and broader accessibility acceptance |
| SAF-032 | Provider-neutral evidence ledger and owner decision checklist | Written data-owner approval, approved policy/authority/retention/residency terms, trained service owners and signed acceptance of all gates |

SAF-029, SAF-031 and SAF-032 remain **incomplete**, even when their local components
pass. No production HA, disaster recovery, legal compliance or independent penetration
test is claimed. The capacity test uses one institution with ten preloaded instruments
against all 100k indexed rows, an in-process ASGI transport and real PostgreSQL.
It does not establish portfolio/dashboard, TLS/network, login, scanning or queue capacity.
Its current gate assesses sampled latency/status; inspect measured arrival/completion
rates separately before concluding that a requested load was achieved.

The evaluation corpus became regression data after it exposed two unsafe amount
proposals; the parser was fixed with failing tests first. Scanned/noisy/multilingual
images explicitly use manual fallback, with zero extracted coverage and 100% abstention.
There is no OCR, model provider, automatic bank verification or AI release decision.
See `evaluation/SAF-026-RESULTS.md` for denominators, strata and current measured timings.

## Final local verification

**272 API tests, 13 workflow browser tests and 2 HTTPS/encryption/accessibility browser tests passed.** TypeScript/Vite build, Ruff and Prettier checks passed. Final dependency audits reported zero known findings; final API/web image scans reported zero HIGH/CRITICAL findings, and the declared source-secret scan reported zero findings. Exact image/archive correspondence and SBOM hashes are recorded. All are time/artifact-specific local checks; full pilot acceptance is still blocked. See TESTING.md for durations, review fixes and measurement scope.

## Evidence locations

Local evidence is deliberately ignored by Git. No raw receipt values or secret values
are copied into a public report.

| Artifact | Scope |
|---|---|
| `.local/evaluation/saf026-final/` | Source/library/corpus/input hashes, metrics, required-test collection, security JUnit/logs |
| `.local/saf027-transit.json` | Real Transit round trip, wrong-context denial, runtime administrative denial |
| `.local/saf027-foundation-evidence.json` | Exact TLS trust anchor, encrypted object versions, runtime DB privilege denials |
| `.local/saf-028-evidence.json` | Audit-integrity and six capture-only alerts |
| `.local/saf-029-evidence.json` | Isolated encrypted database component restore, incomplete DR |
| `.local/saf030-evidence.json` | Declared scoped capacity workload and actual rates/latencies |
| `.local/security/` | Reproducible final dependency/image reports and API/web CycloneDX SBOMs |
| `.local/saf031-source-scan.json` | Separately executed source secret scan; excluded private/generated files |
| `.local/workflow-browser.xml`, `.local/readiness-browser.xml` | Main workflow and HTTPS/readiness browser results |
| `.local/pilot-readiness.json` | Aggregate local statuses, assumptions and unresolved owner gates |

Generated images and package databases change over time: results describe the scanned
artifacts and vulnerability database at execution, not a guarantee against future issues.

## Local operating sequence

See `DEPLOYMENT.md` for exact setup, token renewal and recovery commands. Keep the
existing demo separate from the new `safer_readiness` database, encrypted bucket and
Valkey DB1. Private material is under `~/.local/share/safer-readiness`, outside this
checkout and `.env`; API/worker mounts contain runtime files only, web mounts TLS
files only. Operator recovery keys never enter application mounts. Local single-user
custody is a demonstration, not separation of administration.

Privileged users must carry the Keycloak `safer-mfa-required` role. Keycloak enforces
TOTP and signed ID-token `acr=2`; the API checks that assurance at callback and on
every privileged session use. The app's reviewer plus explicit release grant covers
approvers. Missing assurance denies access rather than silently falling back to a
password. Federation is disabled realm configuration until an approved provider exists.

Browser checks enroll explicitly labelled synthetic test factors. After all checks,
`reset_synthetic_test_mfa.py --synthetic-fixtures-only` removes only those labelled
factors on four fixed local test identities and revokes their local sessions. It
preserves personal/unknown factors and keeps MFA required. A person signing in next
enrolls their own authenticator; generated passwords remain in the private demo-user
file. Never run automated fixture enrollment against a real account.

## Independent review disposition

One independent read-only code review found two important evaluation defects:
self-consistent partial JUnit could pass, and required citations could move to a
different summary section. Regression tests reproduced both before fixes. The runner
now independently collects required test identities, rejects missing/duplicate/skipped
executions and ignores inherited selection options; citation checks require the exact
source set in each section and the release ID belonging to that section.

Deferred minor: source scans are a separate documented invocation rather than part of
`security_scan.sh`; future capacity gates should require achieved rate as well as
sampled latency. Backlog/document consistency was corrected during consolidation.

Review limits stand: live runtime evidence was verified by the implementer, not rerun
by the reviewer; complete DR/platform controls, representative accuracy/human utility,
external federation and malicious same-UID local custodians are not certified. Earlier
SAF-024/025 review remains its own evidence; this review covered their evaluation
integration. Full decisions and the cost of each assumption are in the implementation
plan ledger, `superpowers/plans/2026-10-24-next-phases.md`.

Repeated synthetic browser runs also exposed an older queue truncation: only the first
200 waiting cases were accessible. The review API now uses bounded keyset pages with
current-authority checks, and the UI offers Load more cases. Regression tests cover
complete traversal, no duplicates, invalid/foreign/draft/revoked anchors; the browser
suite exercises the accumulated >200-case fixture inventory. This correction does
not turn the scoped capacity evidence into a whole-portfolio benchmark.
