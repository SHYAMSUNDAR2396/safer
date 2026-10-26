# Security boundary

This application remains local and synthetic. Settings reject production and non-loopback public web/issuer configuration. An explicit local Compose host allowlist supports private backchannels. Docker ports bind loopback. No AICTE certification or legal compliance is claimed. [Pilot readiness](PILOT-READINESS.md) is the current control/gap register.

Implemented: OIDC code+S256 PKCE, state/nonce validation through Authlib, locally provisioned grants, active-user checking each request, hashed opaque sessions with idle/absolute expiry, HttpOnly/SameSite cookies, exact Origin and CSRF checks, per-object institution queries, read-only auditor enforcement, parameterized SQL, strict input validation, exact-decimal money, atomic audit and snapshots, optimistic preconditions + row locks, generated secrets excluded from Git, safe problem responses, API no-store/nosniff/frame/referrer headers.

Untrusted entry points: browser forms/query strings, OIDC responses, session cookies and uploaded files. Identity provider is a separate trust boundary; database is authoritative for membership/grants. Frontend cannot choose tenant or roles. Uploads have signature/type/size/page/pixel/encryption checks in a credential-free CPU/time-limited child, private versioned storage and SHA-256 bindings. Clean files are delivered through an authorized attachment-only endpoint. No LLM ingestion or prompt execution exists.

Local readiness now implements front-door TLS/Secure cookies/CSP, privileged MFA, separate runtime/migration DB roles, Transit-backed object and drill-backup encryption, dependency/container/source checks and component restore/load evidence. Before pilot: approved hosting/retention/residency; trusted public/internal TLS; IdP recovery/logout policy; separate worker/storage identities; independent KMS/backup custody; upstream rate/DDoS controls; parser network isolation; operational SIEM/alert ownership; full restore/load targets; independent assessment and written acceptance. Local DB/broker/identity volume encryption and workstation encryption are outside app verification.

Do not expose Vite, Keycloak start-dev or the object store to a public network. The object store uses one local admin identity; production needs a least-privilege, put/get-only API identity and KMS encryption. Local demo passwords and realm import are plaintext private files by design; never upload them. Account provisioning and identity recovery remain local operator procedures; production federation and cross-organization governance require review. Application logout does not terminate the IdP session, although login forces reauthentication.

SAF-009: malware scanning runs in a credential-free ClamAV container with no internet, storage or database route (verified by `nc` probes, repeated in CI). Clean status is bound to object version + SHA-256 and re-verified at download. Downloads are attachment-only with `Content-Security-Policy: sandbox`. ClamAV is signature-based: a clean verdict means no known signature matched, not that a file is safe or authentic. Downloads use GET with SameSite=Lax cookies; a cross-site link can make a signed-in user download their own institution's clean file, which is audited and exposes nothing to the other site.

SAF-011: reviewers are scoped by explicit assignment, not by token claims or institution; every reviewer route resolves the case through the assignment join and returns 404 otherwise. Evidence methods exclude institution uploads by design. Observation text is rendered as plain text (React escaping, `pre-wrap`), never HTML.

SAF-012: simulator answers are HMAC-signed with a key derived from the local session secret and verified with constant-time comparison; binding to request id, provider, FDR reference, case version and time window is checked before any evidence is written. The simulator is in-process and makes no network calls. It is labelled in UI, data (method, source) and API, and excluded from confirmation counts. Real bank integration remains unauthorised (SAF-036).

SAF-013: the broker requires a generated password and binds to loopback; Celery accepts JSON only, messages carry only a job id, and job payloads are validated against a per-kind schema before any handler runs. Unknown kinds or invalid payloads end as dead without executing.

SAF-015: notifications are visible only to their recipient; recipients are resolved from institution membership and reviewer assignment at generation time. Email goes only to the loopback capture server; settings reject any other host or mode. Email bodies contain the reminder text, FDR reference and bank name; treat captured mail as confidential.

SAF-017: authority is data with expiry, revocation and provenance rather than a role flag. Database constraints enforce dual control/no self-grants. Revocation takes effect on the next request because every scope check queries active grants. Admin sessions share OIDC, CSRF and expiry controls and now require validated MFA assurance (SAF-027 local profile).

SAF-019: release decisions require explicit release authority (SAF-017), separation from clearance work, and a current basis fingerprint; approvals become void on material change. The portal records decisions only; it cannot move money.

SAF-020: execution is evidenced, not performed: SAFER records instructions and independent bank execution evidence and reconciles them; it has no payment capability. Recording execution is separated from approving and instructing.

SAF-022: exports follow OWASP CSV-injection guidance (quote all, neutralise formula prefixes) and are bearer-free: there are no signed links; every download goes through the authenticated, re-authorising endpoint.

SAF-023: PDFs are parsed only in the isolated child process with an empty environment, CPU limit and timeout, and only after a clean malware scan and hash re-check. Extracted text is treated as untrusted data: shown escaped by React, never executed, and never written to a claim without a person saving it.

SAF-024 fallback: reviewer-only scope/revocation checks precede explanation access, including when the feature is disabled. Source notes and snippets never enter narrative templates or execute as instructions. Citations link only to authorized sources inside the open case; React renders facts as text. Evidence/source additions change the basis digest on the next read. No explanation can resolve observations, verify an instrument or approve release. Disable with EXPLANATIONS_ENABLED=false; no remote provider is configured.

SAF-025: the summary route inherits current reviewer assignment checks, including revalidation and disabled responses. Fixed templates treat notes and uploaded text as data; no prompt execution or external AI transfer exists. Exact claim values remain explicitly unconfirmed, simulations are excluded from independent confirmation counts, and summaries cannot mutate decisions. Material digests detect changed source facts; stale/error states hide browser summary facts. Scope revocation is detected on the next validation (15-second interval or focus, subject to browser scheduling); this is not instantaneous remote erasure. All summary responses inherit `Cache-Control: no-store`. No local storage or persisted summary history is used.

Summary revalidation has a 10-second timeout; expired validation hides facts and permits regeneration. After disabling and re-enabling summaries, reload the browser page to clear the disabled snapshot.

## SAF-027–032 local threat boundaries

- **Identity → API:** Authlib validates public issuer/signature, state, nonce and PKCE. The Compose backchannel uses fixed local Keycloak endpoints; it cannot change signed issuer trust. Privileged callbacks require signed `acr=2`, stored in `sessions.mfa_verified`; every request checks role vs assurance. A password-only session promoted to reviewer is denied. Keycloak MFA-role provisioning is required; lack of assurance fails closed. Federation/WebAuthn are not enabled.
- **API → objects → key service:** a fresh AES-256-GCM DEK/nonce encrypts each payload; Transit wraps the DEK using authenticated context. Canonical AAD binds institution/object/bucket/purpose. Only ciphertext, nonce and wrapped key persist in the object envelope; exact-version/hash checks still bind the plaintext record. Tamper/wrong context/legacy plaintext fail closed. This does not encrypt financial metadata in PostgreSQL; approved platform encryption remains required. Plaintext/DEKs exist briefly in process memory; guaranteed zeroization is not claimed.
- **Runtime → operator:** non-root/read-only container profiles and a restricted PostgreSQL role deny DDL, audit updates and instrument deletion. The encrypt/decrypt-only Transit token cannot rotate/delete keys. Private operator/recovery directories are excluded from app mounts. Local API/worker storage credentials remain shared; the single local UID/custodian is trusted and cannot model independent administration.
- **Application → evidence:** source/library/corpus hashes accompany evaluation. Exact per-section citation identities and document versions are checked; security JUnit must match independently collected required identities, without missing/duplicate/skipped tests. Synthetic regression success cannot activate real-data mode.
- **Operations → external effects:** encrypted minimal audit projections and isolated DB restores have measured component evidence. An attacker able to rewrite both local archive and checkpoint defeats single-custodian integrity; independent immutable custody is still required. Restore senders stay disconnected until external effects are reconciled. Alert events are normalized/redacted; actual source connectors and responder assignments remain pending.

No real or anonymized institution data is authorized. Written AICTE data-owner approval,
all pilot controls and a reviewed activation change are prerequisites. Final local
scanner results describe their specific package/image/database versions, not permanent
absence of vulnerabilities. See DEPLOYMENT.md for token expiry, private files and MFA
test-factor cleanup; see the alert runbook for response limitations.

Parser isolation limit: an empty child environment and CPU/timeout bounds do not isolate
its UID/filesystem. A malicious parser exploit could access files readable by the app
UID, including local runtime secret mounts. Synthetic-only operation and production
rejection remain mandatory; pilot requires a separate credential-free filesystem/workload
and network isolation, not merely an empty environment. ClamAV's separate credential-free
network-isolated container is a different boundary.

## Optional LLM boundary

Default off; explicit synthetic egress consent and operator-approved exact source digests required. Provider gets minimized structured data, no tools, credentials, source URLs or free-text observations. Output schema checks do not establish factual truth; original code facts remain authoritative. Post-inference session/grant/source checks and browser polling prevent stale output from being reused as current. Live adversarial evaluation and India-residency approval remain outstanding. See [security and residual risks](design/LLM-INTEGRATION.md).
