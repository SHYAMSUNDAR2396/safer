from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from safer import jobs
from safer.models import Document, Job, JobAttempt
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from test_documents import pdf, upload
from test_instruments import draft


def scan_job(db):
    return db.scalar(select(Job).where(Job.kind == "scan_document"))


def uploaded(clients, actors):
    c = clients()
    item = draft(c, actors)
    return upload(c, item["id"], pdf()).json()


def context(s3, settings):
    return jobs.Context(s3=s3, settings=settings)


def test_upload_enqueues_one_scan_job_in_the_same_transaction(clients, actors, db, s3):
    doc = uploaded(clients, actors)
    job = scan_job(db)
    assert job.payload == {"document_id": doc["id"]} and job.status == "queued"
    assert job.dedup_key == f"scan_document:{doc['id']}"
    jobs.enqueue(db, "scan_document", {"document_id": doc["id"]}, job.dedup_key)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Job)) == 1, "duplicates are absorbed"


def test_enqueue_rolls_back_with_its_business_transaction(db, actors):
    jobs.enqueue(db, "scan_document", {"document_id": str(uuid4())}, "rollback-test")
    db.rollback()
    assert db.scalar(select(func.count()).select_from(Job)) == 0


def test_relay_publishes_once_and_republishes_after_broker_loss(clients, actors, db, s3):
    uploaded(clients, actors)
    sent = []
    assert jobs.publish_due(db, sent.append) == 1
    assert jobs.publish_due(db, sent.append) == 0, "not resent inside the window"
    sent.clear()  # the broker lost the message
    assert jobs.publish_due(db, sent.append, republish_after=timedelta(0)) == 1
    assert sent == [str(scan_job(db).id)]


def test_publish_failure_leaves_job_for_the_next_relay_pass(clients, actors, db, s3):
    uploaded(clients, actors)

    def broker_down(job_id):
        raise ConnectionError("broker unavailable")

    assert jobs.publish_due(db, broker_down) == 0
    assert scan_job(db).published_at is None


def test_run_executes_once_and_ignores_duplicate_delivery(clients, actors, db, s3, settings):
    doc = uploaded(clients, actors)
    job = scan_job(db)
    assert jobs.run(db, job.id, context(s3, settings)) == "succeeded"
    assert jobs.run(db, job.id, context(s3, settings)) == "skipped"
    db.refresh(job)
    assert job.status == "succeeded" and job.attempts == 1
    attempts = db.scalars(select(JobAttempt).where(JobAttempt.job_id == job.id)).all()
    assert [a.outcome for a in attempts] == ["succeeded"]
    listed = clients().get(
        f"/api/v1/instruments/{db.get(Document, doc['id']).instrument_id}/documents"
    )
    assert listed.json()["items"][0]["scan_status"] == "clean"


def test_failures_back_off_then_stop_at_the_attempt_limit(clients, actors, db, s3, settings):
    uploaded(clients, actors)
    job = scan_job(db)
    down = context(s3, settings.model_copy(update={"clamd_port": 1}))
    for attempt in range(1, job.max_attempts + 1):
        db.execute(update(Job).where(Job.id == job.id).values(available_at=func.now()))
        db.commit()
        outcome = jobs.run(db, job.id, down)
        db.refresh(job)
        if attempt < job.max_attempts:
            assert outcome == "retry" and job.status == "queued"
            assert job.available_at > datetime.now(UTC) and job.published_at is None
        else:
            assert outcome == "dead" and job.status == "dead"
    errors = db.scalars(select(JobAttempt.error).where(JobAttempt.job_id == job.id)).all()
    assert len(errors) == job.max_attempts and all(errors)


def test_jobs_not_yet_due_are_neither_published_nor_run(clients, actors, db, s3, settings):
    uploaded(clients, actors)
    job = scan_job(db)
    db.execute(update(Job).values(available_at=datetime.now(UTC) + timedelta(hours=1)))
    db.commit()
    assert jobs.publish_due(db, lambda _: None) == 0
    assert jobs.run(db, job.id, context(s3, settings)) == "skipped"


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("unknown_kind", {}),
        ("scan_document", {"document_id": "not-a-uuid"}),
        ("scan_document", {"document_id": str(uuid4()), "extra": 1}),
    ],
)
def test_unsafe_or_unknown_jobs_are_dead_without_executing(kind, payload, db, actors, s3, settings):
    jobs.enqueue(db, kind, payload, f"bad:{kind}:{len(payload)}")
    db.commit()
    job = db.scalar(select(Job))
    assert jobs.run(db, job.id, context(s3, settings)) == "dead"
    db.refresh(job)
    assert job.status == "dead" and job.last_error


def test_stalled_running_jobs_are_reclaimed(clients, actors, db, s3, settings):
    uploaded(clients, actors)
    job = scan_job(db)
    db.execute(
        update(Job)
        .where(Job.id == job.id)
        .values(status="running", attempts=1, locked_until=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()
    assert jobs.reconcile_stalled(db) == 1
    db.refresh(job)
    assert job.status == "queued" and job.published_at is None
    assert db.scalar(select(JobAttempt.outcome).where(JobAttempt.job_id == job.id)) == "stalled"
    assert jobs.run(db, job.id, context(s3, settings)) == "succeeded"


def test_attempt_history_is_append_only(clients, actors, db, s3, settings):
    uploaded(clients, actors)
    jobs.run(db, scan_job(db).id, context(s3, settings))
    for statement in ("UPDATE job_attempts SET outcome = outcome", "DELETE FROM job_attempts"):
        with pytest.raises(DBAPIError):
            db.execute(text(statement))
        db.rollback()


def test_real_broker_and_worker_deliver_a_scan(clients, actors, db, s3, settings):
    from celery.contrib.testing.worker import start_worker

    doc = uploaded(clients, actors)
    app = jobs.configure(settings)
    with start_worker(app, pool="solo", perform_ping_check=False, shutdown_timeout=10):
        assert jobs.publish_due(db, jobs.celery_publish(app)) == 1
        job = scan_job(db)
        for _ in range(100):
            db.expire_all()
            if db.get(Job, job.id).status == "succeeded":
                break
            import time

            time.sleep(0.1)
    db.expire_all()
    assert db.get(Job, job.id).status == "succeeded"
    assert clients().get(f"/api/v1/documents/{doc['id']}/download").status_code == 200
