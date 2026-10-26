# Local operation and deployment gates

SAFER supports the original loopback API/Vite demo and an additive, portable HTTPS
container readiness profile. Both remain **local, synthetic-only**. `APP_MODE=production`
is rejected. See [pilot gates](PILOT-READINESS.md) before considering any real data.
No public deployment, hosting selection or Kubernetes cluster was created.

## Original local demo

Follow README setup, migrate to head, seed, synchronize identities and configure MFA:

```sh
uv run python scripts/sync_identity.py
uv run python scripts/configure_mfa.py
```

Keep the API, relay and Celery worker running. The relay schedules monitoring and
reconciles queued jobs; a second standalone scanning daemon is unnecessary. Bootstrap
preserves existing generated secrets and identity imports; do not regenerate them
against a retained realm. Privileged users now enroll TOTP at first login. Configure
`safer-mfa-required` for every future reviewer/approver/admin; missing signed LoA2
assurance denies privileged sessions. Old privileged sessions must sign in again.
Application logout revokes its session; IdP login forces reauthentication.

## Portable HTTPS readiness profile

Prerequisites: working original infrastructure/bootstrap, Docker Engine/Compose, Python
3.14/uv, Node 22.12+ and OpenSSL. Images are pinned by digest; builds install lockfiles.
Use only the labelled synthetic fixtures. Commands run from the app root:

```sh
uv sync --locked
uv run alembic upgrade head
uv run alembic -x test=true upgrade head
uv run python scripts/configure_mfa.py
./scripts/compose.sh -f compose.yaml -f compose.readiness.yaml up -d key-service
uv run python scripts/readiness_keys.py
uv run python scripts/readiness_profile.py
(cd apps/web && npm ci)
docker build -f Dockerfile.api -t safer-api:local-readiness .
docker build -f Dockerfile.web -t safer-web:local-readiness .
uv run python scripts/readiness_compose.py
```

If the host has no Buildx plugin, the locally verified classic builder is available
with `DOCKER_BUILDKIT=0` for the two build commands. It is a local tooling workaround,
not a production pipeline recommendation. Wait for PostgreSQL, identity, ClamAV and
API readiness before browser checks; an initial proxy 502 is not a completed startup.

Open **https://localhost:9443**. The local self-signed certificate is generated into
`~/.local/share/safer-readiness/profile/tls`. Browser automation permits this particular
local self-signed setup; `readiness_evidence.py` separately validates the exact trust
anchor rather than disabling TLS validation. Production needs an approved certificate
chain, proxy trust configuration and encryption on internal links.

This profile creates a separate `safer_readiness` DB, migration owner/runtime role,
`safer-readiness-encrypted` bucket and Valkey DB1. The original demo remains on its own
DB/bucket/queue. API and workers are non-root, capability-dropped and read-only apart
from temporary memory. Web serves a production frontend build through Nginx. Keycloak,
PostgreSQL, SeaweedFS, Valkey, ClamAV and Mailpit are shared local infrastructure;
this is not HA or independently administered infrastructure.

### Keys, secrets and factor ownership

All new wrapping-key/recovery material, Transit tokens and TLS keys remain outside
Git and `.env`, in owner-only files under `~/.local/share/safer-readiness`. `.local/readiness-paths.json`
contains paths/UID metadata only. App/worker mounts expose only `profile/app-secrets`;
web sees only `profile/tls`. `profile/operator` and `recovery.json` never enter app
mounts. Local OpenBao has one recovery custodian; independent key/backup administrators,
service authentication, audit-device collection and lost-primary recovery remain gates.

Runtime Transit tokens expire after **one hour** and fail closed. Renew local runtime
access without exporting a token into the environment:

```sh
uv run python scripts/readiness_keys.py
uv run python scripts/readiness_profile.py
```

After a key-service restart the first command unseals the original store using its
original private recovery material. Never reinitialize or delete a store to repair a
missing key. Never discard encrypted-object versions or encryption keys casually.
The adapter rejects legacy plaintext objects rather than silently migrating them.

Browser checks enroll OTP only on fixed synthetic accounts with label `Synthetic test
authenticator`; their private fixture secret cache stays outside the checkout. After
all browser checks, restore human enrollment ownership with:

```sh
PYTHONPATH=apps/api uv run python scripts/reset_synthetic_test_mfa.py --synthetic-fixtures-only
```

It removes only that exact labelled OTP factor from four fixed local subjects, preserves
personal/unknown factors and revokes their local sessions. MFA stays required: next
human login enrolls an authenticator. Do not automate fixture login after replacing
the fixture factor with a personal factor. Passwords remain in private `.local/demo-users.json`.
No password/token/TOTP secret belongs in screenshots, logs, docs or source.

### Federation and future hosting

`infra/keycloak/federation.example.json` is disabled configuration, with a secret
reference and an explicit unconfigured post-broker MFA/recovery requirement. Select and
test the external provider through Keycloak configuration; application authorization
still reads local active membership/grants and signed MFA assurance. No federation
was activated or externally tested. Swap the small `KeyWrapper` interface for the
approved KMS/HSM after contract/security review. Future residency includes India-based
replicas, logs, backups and key services; provider claims remain unverified until selected.

## Health, logs and jobs

`/health/live` checks process liveness; `/health/ready` checks the DB connection. Neither
is a comprehensive scan/key/broker readiness probe. API logs contain request ID, route
template, method, status and duration, not bodies/cookies/identity values. `X-Request-ID`
correlates errors; `Server-Timing` exposes application duration for local measurements.
Inspect dead/old queued jobs and attempts before deliberately requeuing; PostgreSQL is
the outbox ledger, so broker loss does not erase work. Never blindly replay uncertain
notification or release effects. Queue-age alerts and real monitoring ownership remain
pilot work. `clamdb` contains public signatures; failed scans stay quarantined.

## Audit and recovery component drills

Run only against the isolated synthetic readiness profile:

```sh
PYTHONPATH=apps/api uv run python -m safer.local_drills audit
PYTHONPATH=apps/api uv run python -m safer.local_drills recovery
PYTHONPATH=apps/api uv run python scripts/readiness_evidence.py
```

Audit projection backups are encrypted outside app mounts, verified against a separate
checkpoint and tested for alteration/order/gaps. Six synthetic alert rules deliver only
to Mailpit capture. [Response runbook](runbooks/SECURITY-ALERTS.md) defines future
ownership/escalation; real SIEM/retention-lock integrations are not implemented.

Recovery creates a new `safer_restore_synthetic_<12 hex>` DB, never an overwrite or
`--clean` restore. An actual encrypted dump is decrypted and restored; application
counts reconcile. The scratch DB is retained for inspection and has no connected
worker/sender. This **database component passes**, but whole-system recovery remains
incomplete: PITR, object versions, identity, lost keys, independent backup credentials
and full RPO <=1h/RTO <=4h are untested. A DB dump does not include S3 bytes. Preserve
consistent object/version/hash, identity, configuration and key recovery data together.

## Stop, rollback and incidents

`uv run python scripts/readiness_compose.py stop app web-readiness readiness-worker readiness-relay`
stops the new application processes without deleting volumes; original infrastructure
may remain running. Do not use `down -v` to stop normally. Preserve OpenBao and object
volumes together with protected recovery material.

Rollback is a reviewed operation: pause writers/relays, preserve an encrypted backup,
restore the previous tested image digests only if compatible with migration 018 and the
configured object envelope. Prefer forward corrective migrations; do not downgrade
append-only history or expose old privileged sessions. Feature rollback can independently
set `EXPLANATIONS_ENABLED=false` or `SUMMARIES_ENABLED=false`, restart and reload the
browser after re-enabling summaries. No rollback rehearsal is claimed yet.

Incident response: preserve correlation IDs and evidence, contain affected credentials,
revoke both application and identity sessions, and follow the alert/recovery runbook.
Never resume senders on a restored DB before reconciling externally delivered effects.
Real responder assignments, tabletop, upstream DDoS controls and owner acceptance
remain mandatory pilot gates.

## Optional LLM deployment

Keep `LLM_MODE=off` unless the synthetic external-processing exception, private credential/source allowlist and usage budget are approved. Apply migration 019 using the normal migration owner; grant the runtime role access to its ledger. Do not enable via the frontend. A model alias or price change requires reevaluation. See [configuration, rollback and limits](design/LLM-INTEGRATION.md).
