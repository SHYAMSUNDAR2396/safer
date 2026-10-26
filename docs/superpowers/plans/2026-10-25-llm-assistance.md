# SAFER LLM assistance implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task. Track local proof here.

**Goal:** Add optional Gemini-generated advisory wording to existing source-linked explanations and summaries.

**Architecture:** Keep the modular monolith, deterministic status authority, existing case sources and local fallback. Explicit POST generation uses a bounded provider adapter; GET revalidation never calls a model. Provider results are untrusted plain text beside server-rendered facts.

**Tech Stack:** Existing FastAPI, httpx, Pydantic, PostgreSQL, React/TypeScript; Gemini generateContent REST. No added runtime dependency.

**Spec:** User-approved provider/integration proposal in this conversation, 25 October 2026. This file records implementation choices and evidence.

## Global constraints

- Synthetic-only. No live provider call, secret creation, cloud deployment or paid-service activation in this implementation turn.
- Default mode off. Live operation requires explicit synthetic external-processing consent, an owner-only credential file outside the repository and an operator-approved source-digest allowlist. Redaction is not consent or proof of synthetic origin.
- Provider fixed to Gemini 3.5 Flash-Lite; changing models requires evaluation and price review. No arbitrary URL, redirects, tools, search, PDFs or free-text questions.
- Preserve fallback GET routes, code comparison, release decisions and existing local deployment restrictions.
- Preserve all pre-existing uncommitted work. No automatic commit of mixed work.
- Ruling: execute locally in the existing feature branch; creating a clean checkout would omit the accepted uncommitted foundations.

## Review focus

1. Permissions/session revoked during a model request: discard output and recheck current actor and grants.
2. Facts change during generation or after display: source digest check, periodic/focus revalidation and immediate hiding on error.
3. Cross-process spending/races: PostgreSQL serialized admission, durable conservative reservations, no automatic retries or refunds on ambiguous failures.
4. Model returns truncated/tool/foreign block/HTML output: strict envelope validation and plain-text display; no inferred verification.
5. Operator flags alone do not prove data synthetic: allowlist exact purpose/source digests before any outbound call.

## Tasks

### 1. Provider boundary
Files: `safer/llm.py`, `safer/config.py`, `tests/test_llm.py`.
Interface: `Gemini.generate(blocks)` returns validated text keyed by server-issued block ids; `LlmFailure` carries a safe category only. `package(case,purpose)` returns bounded server-owned blocks and a digest.
- [x] Write failing tests for contract, payload minimization, malformed/truncated output, timeouts, credentials and feature gates; observe RED.
- [x] Implement fixed endpoint, bounded requests/responses and protected secret files; observe GREEN.

### 2. Authorized, budgeted generation
Files: `safer/ai.py`, `models.py`, migration `019_llm_attempts.py`, `main.py`, `tests/test_ai.py`.
Interface: GET `/api/v1/reviews/{id}/ai?purpose=summary|explanations`; POST same path with purpose and basis_sha256. All generation uses existing reviewer/CSRF controls and recomputes sources after inference.
- [x] Test default fallback, role/scope/CSRF, changed sources, disabled per-feature flag, exact synthetic approval, durable quota reservation and mid-call revocation.
- [x] Implement metadata-only attempt ledger; conservative fixed 0.03 USD reservation per attempted call with 20KB total request bound and 2048 output-token cap. Monthly default 2 USD, daily 100, per-user 3/minute; one active call across processes. No automatic retries. Bounds are safety limits, not a billing guarantee; independently verify current prices before enabling.
- [x] Re-run backend suite and regenerate OpenAPI.

### 3. Reviewer UI
Files: `apps/web/src/AiAssistance.tsx`, `Review.tsx`, focused Playwright tests.
- [x] Add explicit Explain / Summarize actions and untrusted-AI label, source links, exact server facts and clear fallback reason.
- [x] Hide stale/revoked results with immediate source comparison, 15-second/focus revalidation, aborts and browser timeout.
- [x] Verify browser behavior with mocked external boundary plus build/format checks.

### 4. Documentation and evaluation
- [x] Update API, architecture, security, database, deployment, testing and README; document real-provider evaluation and residency gate as outstanding.
- [x] Run full backend suite and meaningful browser checks; review implementation; record exact outcomes without live-quality claims.

### 5. Controlled demo (pending operator decisions)
- [ ] Explicit India-residency exception for wholly synthetic content, provider account/quota review, credential provision, reviewed exact digest allowlist and budget approval.
- [ ] Live synthetic quality/latency/cost evaluation before enabling demonstration access. Mock tests do not establish model accuracy.

## Execution ledger

Planning: provider research checked official Google model, pricing, structured-output and generateContent documentation. No provider request made. No existing local flags or data altered.


26 October 2026 — local implementation evidence:
- Added fixed Gemini adapter, private-file gates, bounded JSON contract, source minimization and deterministic fallback. No provider requests or credentials were used.
- Added migration 019 to both local synthetic databases, metadata-only usage ledger, explicit GET/POST routes and reviewer UI. Existing financial authority and local-mode restrictions remain intact.
- RED observed for missing provider module and missing AI endpoint. Provider tests then passed. Real PostgreSQL tests prove source/role/session/CSRF controls, source allowlisting, budget persistence, rate limits and cross-process concurrency.
- Fresh independent read-only review found two Important issues: malformed usage metadata escaped fallback; inference required nested pool checkouts. Both reproduced with regression tests and fixed. Single-connection generation and shared two-connection admission now pass. No Critical findings. Live factuality/pricing/residency/latency were explicitly outside that code review and remain rollout gates.
- Full backend suite: 311 passed in 66.45 seconds after review fixes. Final API-focused run: 18 passed in 5.13 seconds. Provider/parser cases: 21 passed in 0.15 seconds.
- Frontend build, full Python lint/format, frontend format and diff whitespace checks passed. Full browser suite subsequently passed: 15 tests in 5.0 minutes (13 established workflows plus 2 AI component tests).
- Initial browser run: 12 passed, 3 failed (shared summary CSS class plus release/dashboard timeouts). CSS cause corrected and full suite rerun; no failed result is counted as success.
- Ruling: no automatic commit/push because substantial accepted prior work is uncommitted in this branch. No deployment, external transfer, live model quality claim or production activation.

- Browser rerun: 15 passed in 5.0 minutes, including reviewer-source refresh, release, dashboard and extraction workflows. The earlier three failures are superseded by this clean full run.

- Final real-API reviewer workflow including explicit AI action: 1 passed in 48.3 seconds. It verified actual session/CSRF wiring, off-mode fallback and original facts without a provider call.
- Cleanup: removed browser-owned MFA factors on 4 fixed synthetic accounts and revoked their test sessions; personal factors preserved. Human privileged users must enroll their own TOTP at next login.
