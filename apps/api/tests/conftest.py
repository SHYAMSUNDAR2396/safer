import hashlib
import secrets
from datetime import UTC, datetime
from pathlib import Path

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from safer.config import Settings
from safer.main import create_app
from safer.models import Grant, Institution, Obligation, SessionRow, User
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
ENV = dotenv_values(ROOT / ".env")


@pytest.fixture
def settings():
    url = ENV["TEST_DATABASE_URL"]
    assert url.endswith("/safer_test"), "Never run destructive fixtures against application data"
    return Settings(database_url=url, s3_bucket="safer-documents-test", redis_db=15)


@pytest.fixture
def db(settings):
    engine = create_engine(settings.database_url.get_secret_value())
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE institutions, users, sessions, obligations, instruments, submissions, documents, document_scans, grants, evidence_records, discrepancies, discrepancy_replies, bank_requests, bank_responses, jobs, job_attempts, reminders, reminder_schedules, notifications, replacement_links, audit_events CASCADE"
            )
        )
        # The migration's default schedule, restored because tests may add versions.
        conn.execute(
            text(
                "INSERT INTO reminder_schedules VALUES (1, '{90,60,30,7}', 30, 7,"
                " '2026-01-01T00:00:00+05:30', 'Illustrative demo schedule')"
            )
        )
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def s3(settings):
    from safer.storage import client, ensure_bucket

    bucket = settings.s3_bucket
    assert bucket.endswith("-test"), "Never empty the application document bucket"
    s3 = client(settings)
    ensure_bucket(s3, bucket)
    for page in s3.get_paginator("list_object_versions").paginate(Bucket=bucket):
        for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
            s3.delete_object(Bucket=bucket, Key=v["Key"], VersionId=v["VersionId"])
    return s3


@pytest.fixture
def actors(db, settings):
    a, b, regulator = (
        Institution(name="Alpha Technical Institute"),
        Institution(name="Beta Technical Institute"),
        Institution(name="Regulation Bureau"),
    )
    db.add_all([a, b, regulator])
    db.flush()
    users = [
        User(
            issuer=settings.oidc_issuer,
            subject=name,
            display_name=name,
            email=f"{name}@example.invalid",
            institution_id=inst.id,
            role=role,
        )
        for name, inst, role in [
            ("alpha", a, "institution_user"),
            ("beta", b, "institution_user"),
            ("auditor", a, "auditor"),
            ("reviewer", regulator, "reviewer"),
            ("admin1", regulator, "admin"),
            ("admin2", regulator, "admin"),
            ("reviewer2", regulator, "reviewer"),
        ]
    ]
    obligations = [
        # Metadata-rule tests need no documents; requirement tests configure their own.
        Obligation(
            institution_id=i.id,
            title="Synthetic obligation",
            required_amount="500000.00",
            required_documents=[],
        )
        for i in (a, b)
    ]
    db.add_all(users + obligations)
    db.flush()
    db.add(
        Grant(
            user_id=users[3].id,
            authority="review",
            institution_id=a.id,
            status="active",
            reason="Test portfolio",
        )
    )
    db.commit()
    return {
        "alpha": users[0],
        "beta": users[1],
        "auditor": users[2],
        "reviewer": users[3],
        "admin1": users[4],
        "admin2": users[5],
        "reviewer2": users[6],
        "obligations": obligations,
    }


@pytest.fixture
def clients(db, actors, settings):
    opened = []

    def login(name="alpha"):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        db.add(
            SessionRow(
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=actors[name].id,
                csrf_token=csrf,
                created_at=now,
                last_seen_at=now,
            )
        )
        db.commit()
        c = TestClient(create_app(settings))
        c.cookies.set("safer_session", token)
        c.headers.update({"Origin": settings.app_origin, "X-CSRF-Token": csrf})
        opened.append(c)
        return c

    yield login
    for c in opened:
        c.close()
        # No lifespan runs without `with TestClient`, so release each app's pool here.
        c.app.state.engine.dispose()
