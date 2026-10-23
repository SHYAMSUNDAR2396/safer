import smtplib
from datetime import date, timedelta

import httpx
import pytest
from pydantic import ValidationError
from safer import deadlines, jobs
from safer.config import Settings
from safer.models import Grant, Job, Notification, User
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from test_deadlines import at, submitted

MAILPIT = "http://127.0.0.1:58025/api/v1"


@pytest.fixture
def mailbox():
    httpx.delete(f"{MAILPIT}/messages", timeout=5).raise_for_status()
    return lambda: httpx.get(f"{MAILPIT}/messages", timeout=5).json()["messages"]


def overdue_case(clients, actors, db):
    """Maturity in 10 days: the action is overdue and escalated at the first sweep."""
    item = submitted(clients(), actors, date.today() + timedelta(days=10))
    deadlines.sweep(db, at(date.today(), 1))
    return item


def mine(db, name, channel="in_app"):
    return db.scalars(
        select(Notification)
        .join(User, User.id == Notification.recipient_id)
        .where(User.subject == name, Notification.channel == channel)
    ).all()


def run_email_jobs(db, s3, settings):
    ids = db.scalars(select(Job.id).where(Job.kind == "send_email")).all()
    return [jobs.run(db, id, jobs.Context(s3=s3, settings=settings)) for id in ids]


def test_reminders_notify_only_in_scope_recipients(clients, actors, db):
    overdue_case(clients, actors, db)
    assert [n.subject for n in mine(db, "alpha")] == ["Renewal action due"]
    assert [n.subject for n in mine(db, "reviewer")] == ["Escalated to reviewer"]
    assert mine(db, "beta") == [] and mine(db, "auditor") == []
    assert len(mine(db, "alpha", "email")) == 1
    assert len(db.scalars(select(Job).where(Job.kind == "send_email")).all()) == 2


def test_inactive_and_unassigned_people_are_not_notified(clients, actors, db):
    submitted(clients(), actors, date.today() + timedelta(days=10))
    db.execute(update(User).where(User.subject == "alpha").values(active=False))
    db.execute(update(Grant).values(status="revoked", revoked_at=func.now()))
    db.commit()
    deadlines.sweep(db, at(date.today(), 1))
    assert db.scalars(select(Notification)).all() == []


def test_inbox_is_private_and_read_state_is_per_user(clients, actors, db):
    overdue_case(clients, actors, db)
    alpha, reviewer = clients(), clients("reviewer")
    inbox = alpha.get("/api/v1/notifications").json()
    assert inbox["unread_count"] == 1 and len(inbox["items"]) == 1
    assert inbox["items"][0]["channel"] == "in_app"
    theirs = reviewer.get("/api/v1/notifications").json()["items"][0]["id"]
    assert alpha.post(f"/api/v1/notifications/{theirs}/read").status_code == 404
    assert alpha.post(f"/api/v1/notifications/{inbox['items'][0]['id']}/read").status_code == 204
    assert alpha.get("/api/v1/notifications").json()["unread_count"] == 0
    assert reviewer.get("/api/v1/notifications").json()["unread_count"] == 1
    alpha.headers.pop("X-CSRF-Token")
    assert alpha.post(f"/api/v1/notifications/{inbox['items'][0]['id']}/read").status_code == 403


def test_email_is_captured_locally_with_traceable_message_id(
    clients, actors, db, s3, settings, mailbox
):
    overdue_case(clients, actors, db)
    assert run_email_jobs(db, s3, settings) == ["succeeded", "succeeded"]
    email = mine(db, "alpha", "email")[0]
    assert email.delivery_status == "sent" and email.delivered_at
    messages = {m["To"][0]["Address"]: m for m in mailbox()}
    assert set(messages) == {"alpha@example.invalid", "reviewer@example.invalid"}
    assert messages["alpha@example.invalid"]["Subject"] == "SAFER: Renewal action due"
    assert str(email.id) in messages["alpha@example.invalid"]["MessageID"]


def test_unreachable_mail_server_retries_then_shows_failed(clients, actors, db, s3, settings):
    item = overdue_case(clients, actors, db)
    down = settings.model_copy(update={"smtp_port": 1})
    for _ in range(3):
        db.execute(update(Job).values(available_at=text("now()")))
        db.commit()
        run_email_jobs(db, s3, down)
    email = mine(db, "alpha", "email")[0]
    assert email.delivery_status == "failed" and email.delivery_detail
    view = clients().get(f"/api/v1/instruments/{item['id']}/deadlines").json()
    deliveries = [d for r in view["reminders"] for d in r["deliveries"]]
    assert {d["status"] for d in deliveries} == {"failed"}


def test_connection_lost_during_send_is_uncertain_and_not_resent(
    clients, actors, db, s3, settings, monkeypatch, mailbox
):
    item = overdue_case(clients, actors, db)

    def drop(self, msg):
        raise smtplib.SMTPServerDisconnected("connection lost during DATA")

    monkeypatch.setattr(smtplib.SMTP, "data", drop)
    assert run_email_jobs(db, s3, settings) == ["succeeded", "succeeded"], "no blind retry"
    email = mine(db, "alpha", "email")[0]
    assert email.delivery_status == "uncertain"
    view = clients().get(f"/api/v1/instruments/{item['id']}/deadlines").json()
    assert "uncertain" in {d["status"] for r in view["reminders"] for d in r["deliveries"]}


def test_real_email_providers_need_separate_authorisation():
    with pytest.raises(ValidationError):
        Settings(email_mode="smtp_provider")
    with pytest.raises(ValidationError):
        Settings(smtp_host="smtp.example.com")


def test_notification_content_cannot_be_rewritten(clients, actors, db):
    overdue_case(clients, actors, db)
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE notifications SET body = 'changed'"))
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM notifications"))
    db.rollback()
