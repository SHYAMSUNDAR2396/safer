# Local operations and future deployment gates

Supported topology is README's loopback API + Vite + Compose database/identity. Lockfiles fix application dependencies; Compose tags fix service versions. No production container build/deployment is supplied in this slice, and changing APP_MODE to production fails validation.

Use `/health/live` for process availability and `/health/ready` for database connection. API emits structured request ID, route template, method, status and duration through the safer logger; no body/cookie/identity values are logged. Correlate X-Request-ID in error responses. Central log aggregation, metrics and alert dashboards remain later backlog work.

Routine stop preserves named volumes. Re-run migration + idempotent seed when restarting a clean app checkout; seed also creates the versioned document bucket. Run `PYTHONPATH=apps/api uv run python -m safer.documents` periodically to fail uploads stuck pending for 15 minutes and remove unbound object versions; no scheduler exists until SAF-013. Do not regenerate identity/password files against an existing realm. Keep secrets outside Git and protect private backups.

Local backup example (from app root):

```sh
umask 077
./scripts/compose.sh exec -T db pg_dump -U safer -d safer -Fc > /tmp/safer-demo-backup.dump
```

Restore into a NEW isolated database, never over the working database. Create `safer_restore`, then pipe backup into `pg_restore -U safer -d safer_restore` through compose exec. Verify counts, scope constraints, immutable history and a user workflow before declaring recovery successful. This runbook is guidance; a disaster-recovery exercise has not been completed. Keycloak identity data and private configuration need a separate consistent backup strategy before pilot.

Rollback: stop app processes, preserve DB dump, return to previous tested source/lockfiles if compatible with schema. Prefer forward corrective migrations; do not blindly downgrade append-only history. No production RPO/RTO is claimed.

Incident triage: record request ID and time without copying secrets; inspect API/Compose service status; distinguish DB outage from identity outage. Restrict local access, revoke affected sessions and disable affected users using an authorized admin procedure. This slice does not include an admin console for these actions; production operational tooling remains a gate.

Document bytes live in the `objectdata` volume, not the database dump. Back up both together and verify that each quarantined record's object version and hash restore; this has not been exercised.

Run the scan worker (`PYTHONPATH=apps/api uv run python -m safer.scanning`, or `--once`) alongside the API. If the worker or ClamAV stops, uploads remain quarantined and show scanning; nothing becomes downloadable. Watch `.local/scanner.log` locally; production needs queue-age and scan-failure alerts (SAF-013/028). `clamdb` holds only public signatures and can be recreated.

Background jobs: run the relay (`python -m safer.jobs`) and a Celery worker (`celery -A safer.worker worker --pool=threads`). Inspect `jobs` for `status = 'dead'` or old `queued` rows; a dead job keeps its last error and its attempts in `job_attempts`. Requeue deliberately with `UPDATE jobs SET status='queued', attempts=0, available_at=now(), published_at=NULL WHERE id=...` after fixing the cause. Losing the Valkey container loses no jobs.

The relay also runs the reminder sweep every minute. To change the schedule, insert a new `reminder_schedules` version with a future `effective_from`; never edit an existing version. A management screen and approval flow belong to SAF-018.
