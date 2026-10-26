# SAF-026 and pilot readiness implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** evaluate the implemented local assistance, then progress through pilot phases in dependency order without confusing local evidence with real-data approval.

**Architecture:** offline Python evaluation CLI reuses the actual isolated parser, extraction rules, comparison and summary builder. A frozen synthetic corpus and independently labelled expected values produce JSON/Markdown metrics; optional real API security regressions have a JUnit evidence trail. No inference provider, new service, business schema or activation change.

**Tech Stack:** existing Python, pypdf, Pillow, pytest, JSON; existing PostgreSQL/S3 integration fixtures.

**Spec:** ../docs/design/NIDHISETU-REQUIREMENTS-ARCHITECTURE-v2.md §8; ../docs/SAFER-IMPLEMENTATION-BACKLOG.md SAF-026–032.

## Global constraints

- User selected local fallback; no external inference or real institutional records.
- Preserve production activation block, existing uncommitted SAF-024/025 work and feature branch.
- No cloud provisioning, deployment, publication or commits in this scope.
- All measurements are actual local results; representative thresholds and manual human baseline require owner input.
- Separate synthetic regression status from pilot acceptance, and report unmeasured queue/cost/utility metrics explicitly.

## Review focus

- Metric denominator errors must not turn abstention into accuracy or hide wrong proposals.
- Missing/skipped/incomplete security evidence must never pass a security gate.
- Corpus alterations, output/library versions and raw-value privacy must remain visible.
- Citations must resolve to the correct source/version, not merely exist.
- Runtime and local synthetic evidence must never remove production gates.

## Task 1 — SAF-026 local evaluation

Files: evaluation/saf026/corpus.json; apps/api/safer/evaluation.py; apps/api/tests/test_evaluation.py; .github/workflows/verify.yml; docs/evaluation/SAF-026.md; README and test/progress/backlog records.

Interfaces: consume extraction.text_lines/extract, reviews.comparison and summaries.state/build. Produce versioned corpus SHA-256, per-field and per-stratum exact-match/critical-error/abstention counters, comparison precision/recall, summary fact/citation checks, actual local p50/p95 runtime and measured security-suite outcome; write machine/human reports with pilot gate blocked pending representative acceptance.

- [x] RED: test scoring of correct/wrong/missing/unexpected proposals, unanswerable fields, percentile rules, citation and summary tampering, missing/failed/skipped JUnit evidence and CLI gate semantics.
- [x] Implement bounded offline corpus runner and strict input validation; generate PDFs safely and evaluate scanned images as explicitly manual-only (no OCR configured).
- [x] Freeze and run independent synthetic layouts/noise/adversarial cases. Report results and any defects; do not silently retune labels to improve scores. A used corpus becomes regression data after fixes.
- [x] Integrate report generation into CI without claiming hosted CI ran.
- [x] Run actual integration security suite, full relevant backend regressions, build/format and one independent read-only review. Fix important findings test-first.
- [x] Record results and representative acceptance gaps before proceeding.

## Task 2 — SAF-027 pilot security foundation

Production hosting/residency, external identity federation, KMS/HSM and owner-approved policy remain undecided. The user explicitly approved provider-neutral local defaults while Task 1 proceeded; implement those without activating production.

- [x] Inspect current topology against SAF-027 and produce a concrete decision/readiness checklist with exact configuration/code gaps.
- [x] User supplied provider-neutral defaults; implement portable local HTTPS/MFA/Transit/restricted-runtime foundation and evidence, keeping platform-specific production changes blocked.
- [x] Until specified, retain local-only activation; do not claim TLS/MFA/KMS/least-privilege production deployment.

## Task 3 — SAF-028–032

Depend on SAF-027. Implement audit/alert integration (028), isolated restore drill (029), declared performance workload (030), independent assessment and CI/security/accessibility checks (031), and owner acceptance (032) in order when dependencies are available. Prepare concrete artifacts where independent; never replace measured platform controls or owner sign-off with generated assertions.

## Ledger

Ruling: retain the current feat/first-slice checkout because the runnable prior slices are uncommitted here; no new worktree would contain them. No worktree or commit is needed for this continuation.
Ruling: a provider-free local evaluation uses existing libraries and synthetic data. Its results cannot certify bank layout generalization, measured human utility, actual cloud cost or pilot readiness; those remain explicitly blocked pending representative data and owner input.
Pre-flight: evaluation reads pure assistance functions and may run pytest on the dedicated test database only; production settings remain untouched. The security subprocess must be serialized against other DB test runs.

User decisions: synthetic-only work; portable containers/Compose; India-resident target (MeitY-empanelled/NIC/MeghRaj to be selected); Keycloak/TOTP for privileged users and configurable federation; OpenBao Transit local adapter, swappable KMS/HSM; no encryption keys in .env/repository; write all assumptions; no provider-specific APIs. This authorizes local preparation for 027–032, not pilot activation.
SAF-026 evidence: initial 138-document/12-review run failed on two unsafe principal proposals; dedicated RED tests reproduced them. text-rules-2 rejects invalid precision/grouping/range. Observed corpus reclassified synthetic_regression; final local evaluation passes with 26 security tests and zero summary/citation errors. Representative holdout/threshold approval remains blocked by absent approved samples.

Progress checkpoint:
- SAF-026: 138 document / 12 review synthetic regression report passes; 26 real API safety regressions; amount precision/range RED→GREEN; initial full suite 252 passed (82.47s), before later readiness additions. CI evaluation added. No representative acceptance claim.
- SAF-027: OpenBao 2.7.1 pinned by digest, Raft volume with one-time owner initialization, runtime encrypt/decrypt-only policy, actual roundtrip/context-denial/admin-denial evidence. Key/unseal/runtime state is now in ~/.local/share/safer-readiness (outside checkout); temporary copy remains outside checkout for recovery. Private app mounts never include operator keys; web mounts TLS files only. Token expires after 1h and must be refreshed through readiness_keys + readiness_profile.
- MFA: additive migration 018 applied to safer and safer_test; new session mfa_verified defaults false. Privileged callback requires validated ID token acr=2; every request rechecks role vs session assurance, so old/elevated sessions reauthenticate. Existing Keycloak browser flow copied, privileged-role condition and LoA2/TOTP enforced. Real reviewer browser workflow passes with TOTP, including replay rejection/next-period retry. All future privileged users must receive the matching Keycloak role as part of provisioning; lack of assurance denies access.
- Separate readiness DB safer_readiness has migration owner and restricted runtime account. Portable API/web images build; https://localhost:9443 verified with its exact self-signed local certificate. Separate encrypted S3 bucket, workers, relay and Valkey DB1 isolate local demo job delivery. HTTPS encrypted upload/scan/submission/reviewer-summary browser test passes. Foundation evidence script verifies exact encrypted versions and runtime DDL/audit-update/instrument-delete denial. Remaining internal TLS, worker/storage separation, parser network isolation and independent custody remain pilot gates.
- SAF-028: local encrypted audit projection + independent digest/chain integrity checks and 6 redacted alert rules delivered to Mailpit capture, verified. Not enterprise SIEM, independent immutable retention or named real responders.
- SAF-029: safe new restore name test RED→GREEN; actual encrypted pg_dump/decrypt/pg_restore to a NEW safer_restore_synthetic_* database. Application table counts reconcile. Result deliberately incomplete: objects/identity/keys were not lost/restored and no whole-system RPO/RTO or independent administrator claim.
- SAF-030: actual scratch DB has 10k synthetic institutions, 100k initial instruments and 10k users. 1000 requests (800 reads/200 writes), 50 scheduled rps / 49.94 completed rps. Header-measured p95 read 30.601 ms, write 29.166 ms; 0 unexpected/server errors. One-institution API scope only, no whole-portfolio/network/OIDC/file/queue/DR/DDOS certification. Scratch DB preserved.
- SAF-031 in progress: Python audit found 37 Pillow12 advisories; upgraded Pillow13, 55 document/parser tests pass, re-audit has no known vulnerabilities. npm audit clean; Trivy source scan has no findings. Original API/web image scans found high/critical OS issues, so images are being rebuilt on patched Alpine and stable Nginx bases. Must re-scan final images and validate musl parser compatibility before claiming green. Axe found contrast + metric label-in-name issues; fixes under test. Independent code review and final full suites still required.

Ruling: new container profile uses an explicit Compose host allowlist and static Keycloak backchannel endpoints while retaining public signed issuer and PKCE/state/nonce checks. APP_MODE remains local-only. Cost: this is not deployment-platform discovery or general external IdP support; federation remains Keycloak configuration after approval.
Ruling: changing Pillow major version is necessary to obtain published security fixes; existing image APIs are retained and parser/scan regressions rerun. Cost: new native wheels and musl compatibility need image-level validation.


Final review: one independent read-only reviewer inspected new/untracked implementation and used pure probes. Important findings: self-consistent partial JUnit can pass; summary citations can move to an unrelated release section. Both accepted as Important. No second review is dispatched.
Final: fixed incomplete security evidence — test_security_runner_ignores_inherited_selection_and_checks_collection reproduced pass on a filtered single test (RED); runner now collects independently, disables inherited selection/plugins, checks exact required identities and duplicate/skipped execution (GREEN). Final full API suite 271/271 in 76.39s.
Final: fixed misplaced summary citations — test_summary_oracle_rejects_unknown_claims_and_misplaced_source_citations reproduced empty errors when Submitted FDR citations moved to Release request (RED); exact per-section sources/release ID required (GREEN). Final full API suite 271/271 in 76.39s.
MFA fixture cleanup: exact-label selector test missing-module RED -> GREEN. Cleanup scope is four fixed synthetic Keycloak subject IDs and the two named loopback demo/readiness databases; preserve personal/unknown factors, leave MFA required, revoke app/IdP fixture sessions. No real identities are reset.
Browser diagnosis: release story contains three fresh reviewer logins and each real TOTP counter can require ~30s; its old 90s override expired after successful closure before final institution check. Increased only that story's budget to 180s, without weakening MFA. A later 120s failure spanned 8.4 wall minutes during a host interruption; rerun with process-scoped idle-sleep prevention. Subsequent launch failure was missing browser cache (all tests 0ms, no app interaction); restored exact locked Playwright browser runtime. Final run is pending below.
Final dependency/security checks: Pillow13 pip-audit 0 known findings, npm audit 0 all severities; final API/web Trivy archives 0 HIGH/CRITICAL, SBOMs written. Docker archive export normalizes image config IDs; verified RootFS diff IDs, configuration and created time exactly equal running image, and scanner ID equals archive config SHA. Local unsigned hashes recorded in .local/security/image-evidence.json; not signed build provenance.
Final: minor (deferred): consolidate the separately documented/executed source secret scan into the same security_scan.sh entrypoint; current CI has its own step and local command/evidence are documented.
Final: minor (deferred): add achieved-rate enforcement to future capacity acceptance; current gate covers sampled latency/status only and report explicitly exposes actual arrival/completion rates and scope. Current measured arrivals were 49.99 of scheduled50 RPS.
Final: Ruling: reviewer did not rerun live runtime tests — retain author-observed Keycloak/TLS/encrypted-object/browser/scan evidence and state its provenance — cost if wrong: code review alone cannot establish deployed behavior.
Final: Ruling: full DR, PITR, independent custody, enterprise SIEM, DDoS, residency and owner acceptance remain blocked — these require selected infrastructure/independent owners and were not simulated into approval — cost if wrong: the system cannot be approved for a real pilot from local evidence.
Final: Ruling: representative accuracy, human utility and full-portfolio/transport capacity remain unproven — synthetic regression/scoped ASGI numbers are labelled as such — cost if wrong: estimated benefits/generalization could fail on real layouts or load.
Final: Ruling: external federation remains disabled config-only — no provider was selected, so no claim of upstream MFA/recovery compatibility — cost if wrong: future integration must be configured and retested before activation.
Final: Ruling: local single-UID custodian remains trusted — private ownership/mode checks and mount boundaries do not defend a malicious same-UID operator rewriting paths — cost if wrong: local operator compromise defeats local isolation; independent administration/workload identity is a pilot prerequisite.
Final: Ruling: SAF-024/025 behavior outside evaluation integration retains its earlier independent review — this review intentionally focused on new readiness code — cost if wrong: any unrelated preexisting defect is not newly certified by this review.

Additional integration defect: accumulated synthetic submissions passed 200 waiting cases; reviewer queue silently truncated them. Browser RED: new submitted reference absent despite valid authority. API RED: test_queue_pages_without_hidden_cases_and_rechecks_anchor_authority expected limit2 but received5. Implemented oldest-first keyset pagination over immutable submission time/id, bounded1..200, reauthorized UUID anchors and additive next_cursor; UI explicit Load more cases. Targeted GREEN plus full suite272/272 in 76.63s. Shared browser helpers traverse visible pages; secondary-session fixture lookup also follows next_cursor (initial undefined lookup reproduced the test fixture's first-page assumption). Final browser rerun pending.

Final main browser evidence:13/13 passed in 6.1m, real Keycloak/TOTP, PostgreSQL, S3 and relay/worker, including >200-case pagination and secondary-session stale-summary checks. Source secret scan0 in declared scope; final runtime image scans0 HIGH/CRITICAL; all Python/Node audit findings0. Build, Ruff91 files, Prettier and diff whitespace checks pass. Full-page explanations/summary screenshot inspected. Final HTTPS/readiness2-test run remains in progress below.

Final HTTPS readiness evidence:2/2 passed in 7.5s on final images; actual encrypted upload/scan/submission, Secure cookie, real TOTP review and automated axe/keyboard checks. Exact TLS/encrypted object/DB least-privilege evidence refreshed after new upload and passed. Removed only labelled test-owned OTP factors on 4 fixed synthetic users after all browser tests; personal factors preserved and MFA stays required. Final phase-evidence.json + pilot-readiness.json record all 7 pilot phases blocked; local029/031/032 explicitly incomplete.
Task1: local synthetic evaluation complete; representative-data acceptance blocked.
Task2: user-approved portable local foundation complete; platform/independent production controls blocked.
Task3: all documented local readiness components implemented/exercised; full029 recovery,031 independent assessment/rollback and032 owner acceptance remain incomplete, never marked pilot-complete.
Final integration: preserve feat/first-slice and uncommitted prior/current work as authorized. No commit, merge, push, publication, production-mode change or deletion of recovery/capacity scratch databases. Plan/evidence retained because no commit exists to recover their record. No further code changes after green final suites; documentation/evidence consolidation only.
