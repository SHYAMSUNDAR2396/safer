# SAFER — Project Guide

**SAFER** = *Secure Administration of FDRs through Electronic Review*. Smart India Hackathon 2026, Problem Statement **SIH26265** (AICTE, Regulation Bureau — Security Deposit / FDR Portal). Earlier working name: *NidhiSetu*.

> **Scope warning.** This is a **local, synthetic-data demonstration**. There is no live bank integration, no payment API, no real data, and `APP_MODE=production` is rejected by the app. Nothing here claims production readiness.

---

## 1. What problem it solves

Educational institutions must keep a security deposit (usually an FDR — a bank's fixed-deposit receipt) with AICTE. Today the evidence is scattered across PDFs, registers and email, and a single "Active" label hides important differences. AICTE needs to know:

- what the institution **claims** vs. what is **independently evidenced**,
- which deadlines (maturity, action, obligation) are coming,
- who owns each pending action,
- whether a **release** was properly authorised, and why.

SAFER is a case-management portal that links every deposit obligation to its instruments, documents, evidence, deadlines and authorised decisions, with a full audit trail.

Core principle: **submitted claims are never treated as bank confirmation.** Evidence is a separate model with source, method, observer and time.

---

## 2. Feature overview

| Area | What it does |
|---|---|
| FDR drafts & submission | Scoped drafts (bank, reference, exact-decimal INR amount, dates). Optimistic locking (`If-Match`), idempotent submit, immutable snapshot + audit in one transaction. |
| Documents | Upload PDF/JPEG/PNG (bounded size/pages/pixels), versioned object storage, **quarantine until ClamAV scan is clean**, audited downloads. Required-document gates before submission. |
| Text extraction | Text-first extraction with source positions; manual fallback (OCR not configured). |
| Review | Reviewer queue limited to assigned institutions; per-field evidence (Match/Mismatch), observations/discrepancies, institution replies, resolution. |
| Bank simulator | Clearly labelled simulator behind a provider interface (replay, stale, timeout scenarios). Timeout ⇒ stays *unconfirmed*. |
| Deadlines & notifications | Separate maturity/action/obligation dates, reminders, in-app + captured email (Mailpit). |
| Replacements | Same-institution successor links, no cycles, no double counting of coverage. |
| Authority & policies | Scoped grants, delegation with expiry/revocation, dual control for admin grants, versioned policies. |
| Release lifecycle | Request → clearances → hold/return/reject/decision → instruction → external execution evidence → close. Approval alone never closes a case; no funds are moved. |
| Dashboard & exports | Scoped counts/amounts with drill-down; async CSV exports (safe cells, expiring, re-authorised on download). |
| Explanations & summaries | Source-linked, rule-based explanations and cited case summaries (local, deterministic). Optional Gemini advisory wording is **off by default**. |
| Security | OIDC + PKCE (Keycloak), server-side authorisation, CSRF + Origin checks, TOTP MFA for privileged roles, encrypted object envelopes (OpenBao Transit in readiness profile). |

---

## 3. Architecture

```
Browser (React) ──cookie+CSRF──▶ Vite dev proxy ──▶ FastAPI (modular monolith)
      │                                                │
      └── OIDC code + PKCE ──▶ Keycloak ◀──discovery───┤
                                                        ├─▶ PostgreSQL (state, audit, job outbox)
                                                        ├─▶ SeaweedFS (S3, versioned, private)
                                                        ├─▶ Valkey/Redis (job delivery only)
 Celery worker ──▶ ClamAV (internal network, no creds) ─┘
 Mailpit (captured email)      OpenBao (key service, readiness profile)
```

Key decisions (full ADRs in `docs/ARCHITECTURE.md`):

- **Modular monolith** — one transaction boundary keeps instrument, snapshot and audit consistent.
- **Local authorisation, not token claims** — OIDC identifies the user; roles/institution come from provisioned local records. Opaque session tokens are hashed in PostgreSQL (30 min idle / 8 h absolute).
- **Row locks + `If-Match` + idempotency keys** for concurrency.
- **PostgreSQL holds job state**; the queue only delivers, so losing queue data loses nothing (outbox + relay).
- **Scanner isolation** — the file scanner has no credentials, DB/storage access or internet.

### Repository layout

```
SIH 2026/
├── SIH26265-research-and-solution-plan.md   Problem research & proposed solution
├── SIH26265-PPT-storyboard.md               Slide storyboard
├── docs/                                    Backlog, design docs (NidhiSetu v2), plans
├── output/                                  Generated pitch decks / slide assets
├── .ppt-build/, .presentation-build/        Deck build scripts (not part of the app)
└── safer/                                   ← THE APPLICATION
    ├── apps/api/safer/    FastAPI backend (one module per domain)
    ├── apps/api/migrations/  Alembic migrations (001…019)
    ├── apps/api/tests/    pytest suite (real PostgreSQL)
    ├── apps/web/src/      React 19 + Vite + TypeScript UI
    ├── apps/web/e2e*/     Playwright tests (demo + readiness)
    ├── scripts/           bootstrap, compose wrapper, MFA/identity, readiness tooling
    ├── infra/             Keycloak federation example, OpenBao, nginx, pilot assumptions
    ├── contracts/openapi.json   API contract
    ├── compose*.yaml      Infrastructure (base / containers / readiness)
    └── docs/              ARCHITECTURE, API, DATABASE, SECURITY, DEPLOYMENT, TESTING, PILOT-READINESS
```

### Backend modules (`apps/api/safer/`)

| Module | Responsibility |
|---|---|
| `main.py`, `config.py`, `db.py`, `errors.py` | App factory, settings (env), DB session, problem+json errors |
| `auth.py`, `security.py` | OIDC login/callback/logout, sessions, CSRF, role guards, MFA assurance |
| `instruments.py`, `schemas.py`, `models.py` | FDR drafts, submissions, audit, validation, ORM |
| `documents.py`, `storage.py`, `filecheck.py`, `scanning.py` | Upload, S3 versions, type/signature checks, ClamAV |
| `extraction.py` | Text extraction with source positions |
| `reviews.py`, `bank.py` | Review cases, evidence, discrepancies; bank simulator |
| `deadlines.py`, `notifications.py`, `jobs.py`, `worker.py` | Reminders, notifications, outbox relay, Celery tasks |
| `replacements.py` | Successor FDR links and coverage |
| `authority.py`, `policies.py`, `releases.py` | Grants/delegation, versioned policies, release workflow |
| `dashboard.py`, `exports.py` | Scoped dashboards, async CSV export |
| `explanations.py`, `summaries.py`, `ai.py`, `llm.py` | Rule-based explanations/summaries; optional LLM advisory |
| `keys.py`, `audit_archive.py`, `capacity.py`, `readiness.py`, `local_drills.py`, `evaluation.py` | Encryption envelopes, audit checkpoints, load/readiness/drill tooling |
| `seed.py`, `fixture_identity.py` | Synthetic institutions, obligations and demo users |

### Main API groups (prefix `/api/v1`; see `docs/API.md` + `contracts/openapi.json`)

`/me`, `/obligations`, `/instruments` (+ `/submissions`, `/audit`, `/documents`, `/deadlines`, `/replacement`, `/release-requests`), `/documents/{id}/download|extraction`, `/reviews` (+ `/evidence`, `/discrepancies`, `/summary`, `/explanations`, `/bank-requests`, `/ai`), `/release-requests/{id}/…` (clearances, hold, resume, return, reopen, decision, instruction, execution, close), `/admin/users|grants|policies`, `/grants/…`, `/notifications`, `/dashboard`, `/exports`. Auth routes: `/auth/login`, `/auth/callback`, `/auth/logout`.

---

## 4. Prerequisites

- Python **3.12+** and [`uv`](https://docs.astral.sh/uv/)
- Node **22.12+**
- Docker Engine + **Compose v2**
- (Readiness profile only) OpenSSL

## 5. Quick start (local demo)

Run everything from `safer/`.

```sh
# 1. One-time setup
python3 scripts/bootstrap.py          # creates .env + random secrets (preserves existing)
uv sync --locked
./scripts/compose.sh up -d            # Postgres, Keycloak, SeaweedFS, Valkey, Mailpit, ClamAV
# wait for Postgres healthy; Keycloak needs ~1 min:
#   http://localhost:8090/realms/safer/.well-known/openid-configuration

# 2. Database + identity
uv run alembic upgrade head
PYTHONPATH=apps/api uv run python -m safer.seed
uv run python scripts/sync_identity.py
uv run python scripts/configure_mfa.py
```

Then start **four** processes (one terminal each):

```sh
# API
uv run uvicorn safer.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --no-access-log

# Job relay (publishes due jobs, reclaims stalled ones)
PYTHONPATH=apps/api uv run python -m safer.jobs

# Celery worker (threads pool on purpose — process pool fails on macOS/Python 3.14)
PYTHONPATH=apps/api uv run celery -A safer.worker worker --pool=threads --concurrency=4

# Frontend
cd apps/web && npm ci && npm run dev
```

| URL | What |
|---|---|
| http://localhost:5173 | The app (use `localhost`, **not** `127.0.0.1`, for OIDC) |
| http://localhost:8090 | Keycloak |
| http://localhost:58025 | Mailpit — captured demo email |

Passwords for demo users are generated into `.local/demo-users.json`. **Never commit or share it.** ClamAV needs ~1 minute after `compose up` before the first scan verdict.

### Demo users

| User | Role / scope |
|---|---|
| `alpha`, `beta` | Institution users of two **separate** institutions |
| `auditor` | Read-only, Alpha only |
| `reviewer` | AICTE reviewer with authority over Alpha only (TOTP required) |
| `reviewer2` | Reviewer with no assignments initially |
| `admin1`, `admin2` | Access admins — release-approval authority needs **both** (dual control) |

No public signup exists. Reviewers/approvers/admins must enrol a TOTP authenticator on first login.

---

## 6. How to use it — guided walkthrough

1. **Sign in as `alpha`** → *New FDR*: synthetic bank name/reference, positive INR amount, ordered dates. Save; edit; reload to confirm persistence.
2. **Upload a document** (small synthetic PDF/JPEG/PNG). Status goes *Quarantined · scanning → Scanned clean* with a Download link. A renamed `.txt` is rejected.
3. **Submit** — confirm. The record locks; the audit timeline shows each transition. Submission is a metadata snapshot only.
4. **Sign out, switch to `beta`** (use Keycloak's *Restart login*): Alpha's records are not visible — tenant isolation.
5. **Sign in as `reviewer`**: Alpha's case is in the queue (Beta's never is). Record independent evidence per field (Match/Mismatch), raise an observation. Optionally open **Source-linked explanations** and **Generate case summary**.
6. **Back as `alpha`**: respond to the observation. **As `reviewer`**: resolve it.
7. **Release flow** (admins/reviewers): request release → clearances → decision (needs authority; two admins for sensitive grants) → instruction → execution evidence → close.
8. **Sign in as `auditor`**: everything readable, nothing writable.
9. **Dashboard / Exports**: scoped counts with drill-down; request a CSV export and download it when ready.

Notes: logout revokes the app session (IdP SSO remains; next login re-authenticates). If your session expires mid-form, use the form's new-tab sign-in link, return and retry — entered data is preserved.

---

## 7. Configuration

All via `.env` (generated by `bootstrap.py`; template in `.env.example`).

| Variable | Purpose |
|---|---|
| `APP_MODE` | Must be `local` |
| `APP_ORIGIN` | e.g. `http://localhost:5173` (Origin/CSRF checks) |
| `DATABASE_URL` / `TEST_DATABASE_URL` | Demo DB / **separate** test DB |
| `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `SESSION_SECRET` | Keycloak + session signing |
| `POSTGRES_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD`, `REDIS_PASSWORD` | Infra secrets |
| `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | Object store |
| `EXPLANATIONS_ENABLED`, `SUMMARIES_ENABLED` | Independent kill-switches for the local rule-based features (set `false` + restart API) |
| `LLM_MODE`, `LLM_SYNTHETIC_EGRESS_APPROVED`, `LLM_API_KEY_FILE`, `LLM_APPROVED_SOURCES_FILE`, `LLM_MONTHLY_BUDGET_MICROUSD` | Optional Gemini advisory (off by default; key lives in a file, never `.env`). See `docs/design/LLM-INTEGRATION.md` |

Do not delete generated secrets while keeping identity volumes: Keycloak imports the realm only on first start.

---

## 8. Testing & verification

```sh
./scripts/compose.sh exec -T db createdb -U safer safer_test   # once
uv run alembic -x test=true upgrade head
uv run pytest -q                              # API tests (truncate safer_test ONLY)
uv run ruff check apps/api scripts
uv run ruff format --check apps/api scripts
cd apps/web
npm run build                                 # type-check + compile
npx playwright install chromium
npm run test:e2e                              # needs API, relay, worker, frontend, compose running
```

API tests need the scanner relay on port 3310. Browser tests leave clearly labelled synthetic records; remove test MFA factors with `scripts/reset_synthetic_test_mfa.py` as described in the operating guide. CI: `.github/workflows/verify.yml`. Security scan helper: `scripts/security_scan.sh`.

---

## 9. Local HTTPS "readiness" profile (optional)

A portable container profile at **https://localhost:9443**: self-signed TLS, non-root/read-only API & web containers, OpenBao Transit for encrypted object envelopes (AES-256-GCM), restricted runtime DB role, isolated DB/bucket/queue.

```sh
uv sync --locked
uv run alembic upgrade head && uv run alembic -x test=true upgrade head
uv run python scripts/configure_mfa.py
./scripts/compose.sh -f compose.yaml -f compose.readiness.yaml up -d key-service
uv run python scripts/readiness_keys.py
uv run python scripts/readiness_profile.py
(cd apps/web && npm ci)
docker build -f Dockerfile.api -t safer-api:local-readiness .
docker build -f Dockerfile.web -t safer-web:local-readiness .
uv run python scripts/readiness_compose.py
```

Keys/TLS/recovery material live in `~/.local/share/safer-readiness` (outside Git). The runtime Transit token **expires after one hour** — renew by re-running `readiness_keys.py` then `readiness_profile.py`. Details: `docs/DEPLOYMENT.md`, evidence and remaining gates: `docs/PILOT-READINESS.md`.

## 10. Free frontend-only preview

Deploy `apps/web` as a Render Static Site: build `npm ci && npm run build`, publish `dist`, set `VITE_PREVIEW_ONLY=true`. Shows a labelled preview with sign-in disabled and no backend calls.

## 11. Stopping and data

- Ctrl-C the API, relay, worker and Vite.
- `./scripts/compose.sh stop` stops infrastructure and **keeps data**.
- Avoid `down -v` unless you intend to wipe all local data. Seed is repeatable and never overwrites FDRs.

## 12. Troubleshooting

| Symptom | Fix |
|---|---|
| Login redirect fails | Use `http://localhost:5173`, not `127.0.0.1`; wait for Keycloak (~1 min) |
| Uploads stay "Quarantined · scanning" | Wait for ClamAV (~1 min); confirm relay + Celery worker are running and port 3310 is up |
| Celery crashes on macOS | Use `--pool=threads` (as above) |
| Privileged login rejected | Enrol TOTP; old privileged sessions must sign in again |
| New Keycloak users missing | `uv run python scripts/sync_identity.py` |
| 502 in readiness profile | Services still starting; wait for Postgres, Keycloak, ClamAV, API |
| Readiness uploads fail after ~1 h | Transit token expired — renew (section 9) |
| Stale/412 on save | Someone else changed the record; reload and retry |

## 13. Roadmap & status

Implemented milestones: **M1** (SAF-001–007 login→draft→submit→audit), **M2** (008–012 documents/evidence/simulator), **M3** (013–016 jobs, deadlines, notifications, replacements), **M4** (017–020 authority, policies, release lifecycle), **M5** (021–025 dashboard, exports, extraction, explanations, summaries), plus readiness SAF-026–032 (evaluation, TLS/MFA/encryption, audit integrity, backup/restore, load test, security checks, pilot-gate ledger).

Still blocked for any real-data pilot: written AICTE data-owner approval, hosting/residency selection (target: MeitY-empanelled Indian cloud / NIC MeghRaj), independent security assessment, independent key custody, immutable audit destination, real bank integration, and ratified policy/authority/retention rules. See `docs/PILOT-READINESS.md` and `../docs/SAFER-IMPLEMENTATION-BACKLOG.md`.

## 14. Further reading

`README.md` · `REQUIREMENTS.md` · `docs/ARCHITECTURE.md` · `docs/API.md` · `docs/DATABASE.md` · `docs/SECURITY.md` · `docs/DEPLOYMENT.md` · `docs/TESTING.md` · `docs/PILOT-READINESS.md` · `docs/runbooks/SECURITY-ALERTS.md` · `../SIH26265-research-and-solution-plan.md`
