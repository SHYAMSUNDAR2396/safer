"""Maturity monitoring.

Three dates stay separate: the FDR's maturity date, the institution's action date (maturity minus
the schedule's lead time) and the obligation's own coverage end. A sweep generates every reminder
that is due by `now` and not yet recorded, so missed runs catch up and repeated runs add nothing.
"""

from datetime import date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from safer.instruments import scoped_instrument
from safer.models import (
    AuditEvent,
    Instrument,
    Obligation,
    Reminder,
    ReminderSchedule,
    ReviewAssignment,
    Submission,
    User,
)
from safer.security import DB, Actor

router = APIRouter(prefix="/api/v1")
IST = ZoneInfo("Asia/Kolkata")
TARGET = timedelta(minutes=15)  # due work must exist within 15 minutes of its due time


def due_at(day: date) -> datetime:
    return datetime.combine(day, time(9, 30), tzinfo=IST)


def active_schedule(db: Session, now: datetime) -> ReminderSchedule | None:
    return db.scalar(
        select(ReminderSchedule)
        .where(ReminderSchedule.effective_from <= now)
        .order_by(ReminderSchedule.version.desc())
        .limit(1)
    )


def renewal_required(maturity: date, required_until: date | None) -> bool:
    return required_until is None or required_until > maturity


def plan(maturity: date, required_until: date | None, schedule) -> list[dict]:
    steps = [
        {
            "step": f"reminder:{days}",
            "kind": "maturity_reminder",
            "owner_role": "institution",
            "day": maturity - timedelta(days=days),
            "message": f"FDR matures on {maturity:%d %b %Y} ({days} days' notice).",
        }
        for days in schedule.offsets_days
    ]
    if renewal_required(maturity, required_until):
        action = maturity - timedelta(days=schedule.action_lead_days)
        steps += [
            {
                "step": "action_due",
                "kind": "action_due",
                "owner_role": "institution",
                "day": action,
                "message": f"Renew or replace this FDR by {action:%d %b %Y}; cover is still required.",
            },
            {
                "step": "escalation",
                "kind": "escalation",
                "owner_role": "reviewer",
                "day": action + timedelta(days=schedule.escalate_after_days),
                "message": f"Renewal action was due on {action:%d %b %Y} and is unresolved.",
            },
        ]
    return sorted(steps, key=lambda s: (s["day"], s["step"]))


def sweep(db: Session, now: datetime | None = None) -> int:
    """Create every due, unrecorded reminder. `now` is injectable as a test clock."""
    now = now or db.scalar(select(func.now()))
    schedule = active_schedule(db, now)
    if not schedule:
        return 0
    horizon = now.astimezone(IST).date() + timedelta(days=max(schedule.offsets_days))
    # ponytail: scans submitted FDRs maturing within the horizon each run; batch by date at scale.
    rows = db.execute(
        select(Instrument, Obligation.required_until, Submission.created_at)
        .join(Obligation, Obligation.id == Instrument.obligation_id)
        .join(Submission, Submission.instrument_id == Instrument.id)
        .where(Instrument.status == "submitted", Instrument.maturity_date <= horizon)
    ).all()
    created = 0
    for item, required_until, submitted_at in rows:
        for step in plan(item.maturity_date, required_until, schedule):
            due = due_at(step["day"])
            if due > now:
                continue
            if step["kind"] == "maturity_reminder" and due < submitted_at:
                continue  # notice periods that ended before submission are moot
            inserted = db.execute(
                insert(Reminder)
                .values(
                    id=uuid4(),
                    instrument_id=item.id,
                    institution_id=item.institution_id,
                    step=step["step"],
                    kind=step["kind"],
                    owner_role=step["owner_role"],
                    schedule_version=schedule.version,
                    due_at=due,
                    generated_at=now,
                    late=now - due > TARGET,
                    message=step["message"],
                )
                .on_conflict_do_nothing(index_elements=["instrument_id", "step"])
                .returning(Reminder.id)
            ).scalar()
            if inserted:
                db.add(
                    AuditEvent(
                        institution_id=item.institution_id,
                        instrument_id=item.id,
                        actor_id=None,
                        action=f"deadline.{step['kind']}",
                        row_version=item.row_version,
                        request_id=str(uuid4()),
                        detail={"step": step["step"], "schedule_version": schedule.version},
                    )
                )
                created += 1
    db.commit()
    return created


def reviewers_for(db: Session, institution_id: UUID) -> list[str]:
    return list(
        db.scalars(
            select(User.display_name)
            .join(ReviewAssignment, ReviewAssignment.reviewer_id == User.id)
            .where(ReviewAssignment.institution_id == institution_id, User.active.is_(True))
            .order_by(User.display_name)
        )
    )


def deadline_view(db: Session, item: Instrument) -> dict:
    now = db.scalar(select(func.now()))
    schedule = active_schedule(db, now)
    required_until = db.get(Obligation, item.obligation_id).required_until
    renewal = renewal_required(item.maturity_date, required_until)
    fired = db.scalars(
        select(Reminder).where(Reminder.instrument_id == item.id).order_by(Reminder.due_at)
    ).all()
    done = {r.step for r in fired}
    upcoming = [
        {"step": s["step"], "kind": s["kind"], "due_at": due_at(s["day"]).isoformat()}
        for s in (plan(item.maturity_date, required_until, schedule) if schedule else [])
        if s["step"] not in done and due_at(s["day"]) > now
    ]
    lead = schedule.action_lead_days if schedule else None
    return {
        "maturity_date": item.maturity_date.isoformat(),
        "action_due_date": (item.maturity_date - timedelta(days=lead)).isoformat()
        if renewal and lead
        else None,
        "obligation_required_until": required_until.isoformat() if required_until else None,
        "renewal_required": renewal,
        "schedule_version": schedule.version if schedule else None,
        "reminders": [
            {
                "step": r.step,
                "kind": r.kind,
                "owner_role": r.owner_role,
                "message": r.message,
                "due_at": r.due_at.isoformat(),
                "generated_at": r.generated_at.isoformat(),
                "late": r.late,
                "schedule_version": r.schedule_version,
            }
            for r in fired
        ],
        "upcoming": upcoming,
        "escalation_owners": reviewers_for(db, item.institution_id),
    }


@router.get("/instruments/{id}/deadlines")
def deadlines(id: UUID, user: Actor, db: DB):
    return deadline_view(db, scoped_instrument(db, user, id))
