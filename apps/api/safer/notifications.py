"""Notifications for generated reminders: in-app inbox plus email to LOCAL CAPTURE only.

Delivery is at-least-once in intent but never claimed exactly-once: a send whose connection
drops during DATA is marked 'uncertain' and not retried, so people see it rather than get
duplicates silently. Each email's Message-ID is the notification id, so duplicates are traceable.
"""

import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage
from uuid import UUID, uuid4

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from safer.authority import active
from safer.errors import Problem
from safer.models import Grant, Notification, User
from safer.security import DB, Actor

router = APIRouter(prefix="/api/v1")
SUBJECTS = {
    "maturity_reminder": "Maturity reminder",
    "action_due": "Renewal action due",
    "escalation": "Escalated to reviewer",
}


def recipients(db: Session, institution_id: UUID, owner_role: str) -> list[User]:
    if owner_role == "reviewer":
        query = (
            select(User)
            .join(Grant, Grant.user_id == User.id)
            .where(Grant.institution_id == institution_id, active("review"))
        )
    else:  # institution officers act on reminders; auditors are read-only observers
        query = select(User).where(
            User.institution_id == institution_id, User.role == "institution_user"
        )
    return list(db.scalars(query.where(User.active.is_(True)).order_by(User.display_name)))


def fanout(db: Session, reminder_id: UUID, item, kind: str, owner_role: str, message: str):
    """Create notifications in the reminder's transaction; emails are queued as outbox jobs."""
    from safer.jobs import enqueue  # jobs registers this module's handler

    body = (
        f"{message}\nFDR {item.bank_reference} · {item.bank_name}\n\nSynthetic SAFER demonstration."
    )
    for user in recipients(db, item.institution_id, owner_role):
        for channel in ("in_app", "email") if user.email else ("in_app",):
            created = db.execute(
                insert(Notification)
                .values(
                    id=uuid4(),
                    instrument_id=item.id,
                    institution_id=item.institution_id,
                    reminder_id=reminder_id,
                    recipient_id=user.id,
                    channel=channel,
                    subject=SUBJECTS[kind],
                    body=body,
                    delivery_status="pending" if channel == "email" else "not_applicable",
                    delivery_detail="",
                )
                .on_conflict_do_nothing(index_elements=["reminder_id", "recipient_id", "channel"])
                .returning(Notification.id)
            ).scalar()
            if created and channel == "email":
                enqueue(
                    db, "send_email", {"notification_id": str(created)}, f"send_email:{created}"
                )


class EmailPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    notification_id: UUID


def send_email(db: Session, ctx, payload: EmailPayload, final: bool):
    from safer.jobs import Retry

    n = db.scalar(
        select(Notification)
        .where(Notification.id == payload.notification_id, Notification.channel == "email")
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not n or n.delivery_status != "pending":
        db.rollback()
        return  # already settled: a duplicate delivery of this job sends nothing
    settings, to = ctx.settings, db.get(User, n.recipient_id).email
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.mail_from, to, f"SAFER: {n.subject}"
    msg["Message-ID"] = f"<{n.id}@safer.invalid>"
    msg.set_content(n.body)
    in_data = False
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.mail(settings.mail_from)
            code, reply = smtp.rcpt(to)
            if code >= 400:
                raise smtplib.SMTPRecipientsRefused({to: (code, reply)})
            in_data = True
            smtp.data(msg.as_bytes())
        n.delivery_status, n.delivery_detail = "sent", "accepted by local capture server"
        n.delivered_at = datetime.now(UTC)
    except (OSError, smtplib.SMTPException) as e:
        permanent = getattr(e, "smtp_code", 0) >= 500 or isinstance(
            e, smtplib.SMTPRecipientsRefused
        )
        if in_data and not permanent:
            n.delivery_status = "uncertain"
            n.delivery_detail = "connection lost while sending; may or may not have arrived"
        elif permanent or final:
            n.delivery_status, n.delivery_detail = "failed", f"not delivered ({type(e).__name__})"
        else:
            db.rollback()
            raise Retry(f"mail server unavailable ({type(e).__name__})")
    db.commit()


def deliveries(db: Session, reminder_ids) -> dict:
    rows = db.execute(
        select(Notification, User.display_name)
        .join(User, User.id == Notification.recipient_id)
        .where(Notification.reminder_id.in_(reminder_ids), Notification.channel == "email")
        .order_by(User.display_name)
    ).all()
    result: dict = {}
    for n, name in rows:
        result.setdefault(n.reminder_id, []).append(
            {
                "recipient": name,
                "channel": "email",
                "status": n.delivery_status,
                "detail": n.delivery_detail,
            }
        )
    return result


@router.get("/notifications")
def inbox(user: Actor, db: DB):
    mine = (Notification.recipient_id == user.id) & (Notification.channel == "in_app")
    rows = db.scalars(
        select(Notification).where(mine).order_by(Notification.created_at.desc()).limit(50)
    ).all()
    unread = db.scalar(select(func.count()).where(mine, Notification.read_at.is_(None)))
    return {
        "unread_count": unread,
        "items": [
            {
                "id": str(n.id),
                "instrument_id": str(n.instrument_id),
                "channel": n.channel,
                "subject": n.subject,
                "body": n.body,
                "created_at": n.created_at.isoformat(),
                "read": n.read_at is not None,
            }
            for n in rows
        ],
    }


@router.post("/notifications/{id}/read", status_code=204)
def mark_read(id: UUID, user: Actor, db: DB):
    n = db.scalar(
        select(Notification).where(
            Notification.id == id,
            Notification.recipient_id == user.id,
            Notification.channel == "in_app",
        )
    )
    if not n:
        raise Problem(404, "not_found", "Notification not found.")
    n.read_at = n.read_at or datetime.now(UTC)
    db.commit()
    return Response(status_code=204)
