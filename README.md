# SAFER — FDR lifecycle portal

Secure Administration of FDRs through Electronic Review, AICTE PS26265.

**Local synthetic demonstration only.** Includes scoped FDR drafts/submissions, versioned documents, isolated scanning, required-document gates, text extraction, reviewer evidence and discrepancies, a labelled bank simulator, renewals/reminders, governed release tracking, dashboards and protected CSV exports. Source-linked explanations and summaries default to local rules; optional Gemini advisory wording is disabled until explicitly configured and approved for synthetic processing. Submitted claims remain separate from independent evidence. No live bank integration, payment API or production readiness is claimed.

## Start locally

Prerequisites: Python 3.12+, uv, Node 22.12+ (verified with Node 26), Docker engine and Compose v2. Run from this directory:

```sh
python3 scripts/bootstrap.py
uv sync --locked
./scripts/compose.sh up -d
uv run alembic upgrade head
PYTHONPATH=apps/api uv run python -m safer.seed
uv run python scripts/sync_identity.py
uv run python scripts/configure_mfa.py
```

Bootstrap also adds object-store credentials to an existing `.env` without touching other secrets; re-run it after pulling this change. Wait for PostgreSQL to become healthy before migrations. Keycloak may take about a minute to start; check `http://localhost:8090/realms/safer/.well-known/openid-configuration`. Bootstrap creates random private secrets; it preserves existing `.env`. Do not delete generated secrets while preserving identity volumes: Keycloak imports the realm only when new.

Start API in a terminal:

```sh
uv run uvicorn safer.main:app --app-dir apps/api --host 127.0.0.1 --port 8000 --no-access-log
```

Start background jobs in two more terminals (ClamAV needs about a minute after `compose up` before its first verdict):

```sh
PYTHONPATH=apps/api uv run python -m safer.jobs          # relay: publishes due jobs, reclaims stalled ones
PYTHONPATH=apps/api uv run celery -A safer.worker worker --pool=threads --concurrency=4
```

The thread pool is deliberate: jobs are I/O-bound, and Celery's default process pool fails on macOS with Python 3.14. `python -m safer.scanning` remains as a one-shot manual recovery command.

Start frontend in another terminal:

```sh
cd apps/web
npm ci
npm run dev
```

Captured demo email is visible at **http://localhost:58025** (Mailpit; nothing leaves the machine).

Open **http://localhost:5173** (use `localhost`, not `127.0.0.1`, for OIDC). Open `.local/demo-users.json` locally for generated passwords. Never commit or share that file. `alpha` and `beta` belong to separate institutions. `auditor` has read-only access to Alpha. `reviewer` is an AICTE reviewer with review authority over Alpha only; `reviewer2` starts with none. `admin1` and `admin2` are access administrators: release-approval authority needs both. `sync_identity.py` adds users created after your Keycloak was first initialised; it is a no-op otherwise. No public signup exists.

Reviewers, approvers and admins require TOTP enrollment and signed MFA assurance. Old privileged sessions must sign in again. After automated browser tests, remove only labelled synthetic test factors as described in the operating guide so the next human login can enroll its own authenticator.

## Local readiness profile

A separate portable container profile runs at **https://localhost:9443**, with a local self-signed certificate, encrypted object envelopes via OpenBao Transit, a restricted runtime DB account and isolated synthetic DB/bucket/queue. Keys and recovery material live outside the checkout and `.env`. Follow [setup and operations](docs/DEPLOYMENT.md); the runtime key token needs renewal after one hour.

[Pilot readiness](docs/PILOT-READINESS.md) records SAF-026–032 local evidence, assumptions and remaining gates. The [synthetic evaluation](docs/evaluation/SAF-026-RESULTS.md) covers 138 receipts and 12 review cases; scans use manual entry because OCR is not configured. Local security checks, alert/restore drills and scoped load results do not approve real data or activate production.

## Try the slice

1. Sign in as alpha, choose New FDR, enter synthetic bank/reference, positive INR amount and ordered dates.
2. Save and edit the draft. Reload to confirm PostgreSQL persistence.
3. On the draft, upload a small synthetic PDF/JPEG/PNG: it shows Quarantined · scanning, then Scanned clean with a Download link; the audit trail records upload, scan and download. A renamed text file is rejected.
4. Submit metadata; confirm. The record locks and its audit timeline shows each transition.
5. Sign out, use Keycloak's Restart login control to switch to beta: Alpha's records are absent.
7. Sign in as reviewer: the Alpha case is in the review queue (Beta's never is). Record independent evidence per field and see Match/Mismatch; raise an observation. Sign back in as alpha to respond, then as reviewer to resolve.
6. Sign in as auditor: records can be read, not created or changed.

Logout revokes the app session; IdP SSO remains. Next login requires reauthentication. If a session expires during entry, sign in through the form's new-tab link, then return and retry; same-account checks protect the retained form.

## Verify

Create the separate test database once (do not substitute the demo database):

```sh
./scripts/compose.sh exec -T db createdb -U safer safer_test
uv run alembic -x test=true upgrade head
uv run pytest -q
uv run ruff check apps/api scripts
uv run ruff format --check apps/api scripts
cd apps/web
npm run build
npx playwright install chromium
npm run test:e2e
```

API tests truncate **safer_test only**. Browser tests use the running local demo and leave clearly labeled synthetic records. API, job relay, Celery worker, frontend and Compose services must be running for browser tests; API tests need the scanner relay on port 3310. Test passwords are read locally, never embedded in source. Frontend build is type-check plus compilation, not a production-readiness assertion.

## Stop / preserve data

Stop API and Vite with Ctrl-C. `./scripts/compose.sh stop` stops infrastructure and preserves volumes. Do not use `down -v` unless intentionally discarding local data. Seed is repeatable and does not overwrite FDRs.

## Free frontend preview

The frontend can be published as a free Render Static Site. Select `apps/web`
as the root directory, `npm ci && npm run build` as the build command, and
`dist` as the publish directory. Set `VITE_PREVIEW_ONLY=true` before building.
This displays a clearly labelled preview with sign-in disabled and makes no
backend requests. Login, uploads, saved records and review actions are unavailable.
No API secrets or local `.env` files are needed. Omit this setting for the
existing full local demo; it does not enable public backend deployment.

## Documentation

- `REQUIREMENTS.md` — implemented acceptance scope
- `docs/ARCHITECTURE.md` — boundaries and decisions
- `docs/API.md`, `contracts/openapi.json` — API contract
- `docs/DATABASE.md` — schema and transaction boundaries
- `docs/SECURITY.md` — controls and remaining gates
- `docs/DEPLOYMENT.md` — operations and recovery
- `docs/PILOT-READINESS.md` — measured local evidence and blocked pilot gates
- `docs/TESTING.md` — reproducible validation
- `../docs/SAFER-IMPLEMENTATION-BACKLOG.md` — complete prioritized roadmap

## Source-linked explanations (SAF-024 fallback)

Sign in as an assigned reviewer, open a submitted case and expand **Source-linked explanations**. Expand **Sources and versions** to jump to the cited submission, evidence or institution document. The view reuses deterministic comparison rules and explains simulation/document limits. Refresh sources after new evidence. Set `EXPLANATIONS_ENABLED=false` and restart the API to remove the feature independently. No model or external provider is configured.

## Cited case summaries (SAF-025 local fallback)

Assigned reviewers can open a submitted case and choose **Generate case summary**. It copies exact claim values, counts recorded evidence separately from simulations, cites frozen document versions, and lists observations, deadlines and release status. Expand **Sources and versions** to inspect records. Material case changes hide the old facts with **Summary stale** until explicit regeneration. Current summaries revalidate every 15 seconds and on window focus; failed revalidation hides summary facts. Set `SUMMARIES_ENABLED=false` and restart the API to disable summaries independently of explanations. No model or external AI service is used; summaries never authorize release.

Summary revalidation has a 10-second timeout; expired validation hides facts and permits regeneration. After disabling and re-enabling summaries, reload the browser page to clear the disabled snapshot.

## Optional LLM assistance

Gemini advisory explanations and summaries are available behind an off-by-default gate. Local fallback remains the default. See [integration and enablement](docs/design/LLM-INTEGRATION.md); no live model evaluation or data-transfer approval is implied.
