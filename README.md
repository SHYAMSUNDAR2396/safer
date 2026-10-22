# SAFER — first working slice

Secure Administration of FDRs through Electronic Review, AICTE PS26265.

**Local synthetic demonstration only.** Real OIDC login, institution-scoped FDR drafts, edits, metadata submission, immutable snapshots, transactional audit and document upload with isolated malware scanning and audited download are implemented. Mandatory documents, bank verification, renewals, alerts and releases are future milestones. Submitted metadata is always unverified. This is not production-ready.

## Start locally

Prerequisites: Python 3.12+, uv, Node 22.12+ (verified with Node 26), Docker engine and Compose v2. Run from this directory:

```sh
python3 scripts/bootstrap.py
uv sync --locked
./scripts/compose.sh up -d
uv run alembic upgrade head
PYTHONPATH=apps/api uv run python -m safer.seed
uv run python scripts/sync_identity.py
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

Open **http://localhost:5173** (use `localhost`, not `127.0.0.1`, for OIDC). Open `.local/demo-users.json` locally for generated passwords. Never commit or share that file. `alpha` and `beta` belong to separate institutions. `auditor` has read-only access to Alpha. `reviewer` is an AICTE reviewer assigned to Alpha only. `sync_identity.py` adds users created after your Keycloak was first initialised; it is a no-op otherwise. No public signup exists.

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

## Documentation

- `REQUIREMENTS.md` — implemented acceptance scope
- `docs/ARCHITECTURE.md` — boundaries and decisions
- `docs/API.md`, `contracts/openapi.json` — API contract
- `docs/DATABASE.md` — schema and transaction boundaries
- `docs/SECURITY.md` — controls and remaining gates
- `docs/DEPLOYMENT.md` — operations and recovery
- `docs/TESTING.md` — reproducible validation
- `../docs/SAFER-IMPLEMENTATION-BACKLOG.md` — complete prioritized roadmap
