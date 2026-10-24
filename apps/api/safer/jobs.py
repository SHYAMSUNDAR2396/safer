"""Durable background jobs.

PostgreSQL is the source of truth: `enqueue` writes a job row in the caller's transaction (outbox).
The relay publishes due job ids to Celery over Valkey; workers claim a job with one atomic status
change, so duplicate or late deliveries are skipped and a lost message is simply republished.
Every attempt is recorded. Delivery is at-least-once; handlers must be idempotent.
"""

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from celery import Celery
from kombu.exceptions import OperationalError
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from safer import exports, notifications, scanning
from safer.models import Job, JobAttempt

# All job timestamps use the database clock: host and container clocks can drift apart.
LEASE = timedelta(minutes=5)
REPUBLISH_AFTER = timedelta(minutes=1)


class Retry(Exception):
    """A handler's temporary failure: retried with backoff until max_attempts."""


@dataclass
class Context:
    s3: object
    settings: object


class ScanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID


def scan_handler(db: Session, ctx: Context, payload: ScanPayload, final: bool):
    if scanning.scan_document(db, ctx.s3, ctx.settings, payload.document_id) == "error":
        raise Retry("scanner or storage unavailable")


# kind -> (payload schema, handler). Payloads are JSON validated per kind; nothing is unpickled.
HANDLERS = {
    "scan_document": (ScanPayload, scan_handler),
    "send_email": (notifications.EmailPayload, notifications.send_email),
    "build_export": (exports.ExportPayload, exports.build),
}


def enqueue(db: Session, kind: str, payload: dict, dedup_key: str, max_attempts: int = 3):
    """Add a job inside the caller's transaction; an existing dedup_key makes this a no-op."""
    db.execute(
        insert(Job)
        .values(
            id=uuid4(),
            kind=kind,
            payload=payload,
            dedup_key=dedup_key,
            status="queued",
            attempts=0,
            max_attempts=max_attempts,
            last_error="",
        )
        .on_conflict_do_nothing(index_elements=["dedup_key"])
    )


def publish_due(db: Session, publish, republish_after=REPUBLISH_AFTER, limit=100) -> int:
    """Send due job ids; anything unacknowledged by a claim is resent after `republish_after`."""
    due = db.scalars(
        select(Job)
        .where(
            Job.status == "queued",
            Job.available_at <= func.now(),
            or_(Job.published_at.is_(None), Job.published_at < func.now() - republish_after),
        )
        .order_by(Job.available_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    sent = 0
    for job in due:
        try:
            publish(str(job.id))
        except (OSError, OperationalError):
            break  # broker unavailable: the next relay pass retries
        job.published_at = func.now()
        sent += 1
    db.commit()
    return sent


def backoff(attempt: int) -> timedelta:
    return min(timedelta(seconds=30 * 2 ** (attempt - 1)), timedelta(minutes=15))


def _finish(db: Session, job_id, attempt: int, outcome: str, error: str, started) -> str:
    values = {"locked_until": None, "last_error": error[:300]}
    if outcome == "retry":
        values |= {
            "status": "queued",
            "published_at": None,
            "available_at": func.now() + backoff(attempt),
        }
    else:
        values["status"] = outcome
    db.execute(update(Job).where(Job.id == job_id, Job.status == "running").values(**values))
    db.add(
        JobAttempt(
            job_id=job_id, attempt=attempt, outcome=outcome, error=error[:300], started_at=started
        )
    )
    db.commit()
    return outcome


def run(db: Session, job_id, ctx: Context) -> str:
    """Claim and execute one job; returns succeeded, retry, dead or skipped."""
    started = datetime.now(UTC)
    claimed = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == "queued", Job.available_at <= func.now())
        .values(status="running", attempts=Job.attempts + 1, locked_until=func.now() + LEASE)
        .returning(Job.attempts, Job.max_attempts, Job.kind, Job.payload)
    ).first()
    db.commit()
    if not claimed:
        return "skipped"  # duplicate, late or not yet due
    attempt, max_attempts, kind, payload = claimed
    try:
        schema, handler = HANDLERS[kind]
        data = schema.model_validate(payload)
    except (KeyError, ValidationError) as e:
        return _finish(
            db, job_id, attempt, "dead", f"unknown or invalid job ({type(e).__name__})", started
        )
    try:
        handler(db, ctx, data, final=attempt >= max_attempts)
        return _finish(db, job_id, attempt, "succeeded", "", started)
    except Retry as e:
        error = str(e)
    except Exception as e:  # a crashing handler is recorded and retried, never silently lost
        db.rollback()
        error = f"handler failed ({type(e).__name__})"
    return _finish(
        db, job_id, attempt, "dead" if attempt >= max_attempts else "retry", error, started
    )


def reconcile_stalled(db: Session) -> int:
    """Requeue (or end) jobs whose worker vanished after claiming them."""
    stalled = db.scalars(
        select(Job)
        .where(Job.status == "running", Job.locked_until < func.now())
        .with_for_update(skip_locked=True)
    ).all()
    for job in stalled:
        error = "worker stopped before finishing"
        db.add(JobAttempt(job_id=job.id, attempt=job.attempts, outcome="stalled", error=error))
        job.status = "dead" if job.attempts >= job.max_attempts else "queued"
        job.locked_until, job.published_at, job.last_error = None, None, error
        job.available_at = func.now()
    db.commit()
    return len(stalled)


def configure(settings=None) -> Celery:
    """Celery app whose single task runs a job id against PostgreSQL."""
    from sqlalchemy import create_engine

    from safer.config import Settings
    from safer.storage import client

    settings = settings or Settings()
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    ctx = Context(s3=client(settings), settings=settings)
    app = Celery("safer", broker=settings.broker_url)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        task_ignore_result=True,
        task_acks_late=True,
        task_publish_retry=False,
        broker_connection_retry_on_startup=True,
        worker_hijack_root_logger=False,
    )

    @app.task(name="safer.run_job")
    def run_job(job_id: str):
        with Session(engine, expire_on_commit=False) as db:
            return run(db, UUID(job_id), ctx)

    return app


def celery_publish(app: Celery):
    return lambda job_id: app.send_task("safer.run_job", args=[job_id])


if __name__ == "__main__":
    # Relay: publish due jobs and reclaim stalled ones. Run alongside `celery -A safer.worker worker`.
    from sqlalchemy import create_engine

    from safer import deadlines
    from safer.config import Settings
    from safer.storage import client

    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    publish, s3 = celery_publish(configure(settings)), client(settings)
    swept = 0.0
    while True:
        with Session(engine, expire_on_commit=False) as session:
            sent, stalled = publish_due(session, publish), reconcile_stalled(session)
            reminders = 0
            if time.monotonic() - swept >= 60:  # well inside the 15-minute due-work target
                reminders, swept = deadlines.sweep(session), time.monotonic()
                exports.purge(session, s3, settings)
        if sent or stalled or reminders:
            print(
                json.dumps({"published": sent, "stalled": stalled, "reminders": reminders}),
                flush=True,
            )
        time.sleep(2)
