"""Scoped dashboard. Every metric has one grain: a count of FDRs and the sum of their principal.

Each metric is a single SQL definition used for both its total and its drill-down list, so the
two always agree. Scope: institution users and auditors see their institution; reviewers see the
institutions they hold any active authority over; administrators hold none and see nothing.
"""

from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from safer.authority import active
from safer.errors import Problem
from safer.models import (
    Discrepancy,
    DiscrepancyReply,
    Grant,
    Institution,
    Instrument,
    Obligation,
    ReleaseClearance,
    ReleaseInstruction,
    ReleaseRequest,
    Reminder,
    ReplacementLink,
)
from safer.replacements import coverage_view
from safer.security import DB, Actor

router = APIRouter(prefix="/api/v1")
GRAIN = "Count of FDRs; amount is the sum of their principal (INR) as submitted."


def scope(db: Session, user) -> list[UUID]:
    if user.role in ("institution_user", "auditor"):
        return [user.institution_id]
    if user.role == "reviewer":
        return list(
            db.scalars(
                select(Grant.institution_id).where(Grant.user_id == user.id, active()).distinct()
            )
        )
    return []


def _live_replacement():
    return exists().where(
        ReplacementLink.predecessor_id == Instrument.id,
        ReplacementLink.status.in_(("proposed", "accepted")),
    )


def _reminder(kind):
    return and_(
        exists().where(Reminder.instrument_id == Instrument.id, Reminder.kind == kind),
        ~_live_replacement(),
    )


def _release(*conditions):
    return exists().where(ReleaseRequest.instrument_id == Instrument.id, *conditions)


_cleared = (
    select(func.count())
    .where(ReleaseClearance.request_id == ReleaseRequest.id)
    .correlate(ReleaseRequest)
    .scalar_subquery()
)
_required = func.jsonb_array_length(ReleaseRequest.policy_snapshot["rules"]["clearances"])
_instructed = exists().where(ReleaseInstruction.request_id == ReleaseRequest.id)
_open_observation = exists().where(
    Discrepancy.instrument_id == Instrument.id,
    ~exists().where(
        DiscrepancyReply.discrepancy_id == Discrepancy.id, DiscrepancyReply.kind == "resolution"
    ),
)


def definitions(today: date):
    submitted = Instrument.status == "submitted"
    return [
        # key, group, label, condition, institution-only
        ("draft", "Portfolio", "Drafts", Instrument.status == "draft", True),
        ("active", "Portfolio", "Submitted and active", submitted, False),
        ("closed", "Portfolio", "Released and closed", Instrument.status == "closed", False),
        (
            "maturing_30",
            "Needs attention",
            "Maturing within 30 days",
            and_(submitted, Instrument.maturity_date.between(today, today + timedelta(days=30))),
            False,
        ),
        (
            "matured_uncovered",
            "Needs attention",
            "Matured while cover is still required",
            and_(
                submitted,
                Instrument.maturity_date < today,
                or_(
                    Obligation.required_until.is_(None),
                    Obligation.required_until > Instrument.maturity_date,
                ),
                ~exists().where(
                    ReplacementLink.predecessor_id == Instrument.id,
                    ReplacementLink.status == "accepted",
                ),
            ),
            False,
        ),
        (
            "action_overdue",
            "Needs attention",
            "Renewal action due",
            and_(submitted, _reminder("action_due")),
            False,
        ),
        (
            "escalated",
            "Needs attention",
            "Escalated to reviewer",
            and_(submitted, _reminder("escalation")),
            False,
        ),
        (
            "open_observations",
            "Needs attention",
            "Open reviewer observations",
            and_(submitted, _open_observation),
            False,
        ),
        (
            "releases_clearing",
            "Release work",
            "Releases awaiting clearances",
            _release(
                ReleaseRequest.status.in_(("open", "on_hold", "returned")), _cleared < _required
            ),
            False,
        ),
        (
            "releases_ready",
            "Release work",
            "Releases ready for decision",
            _release(ReleaseRequest.status == "open", _cleared >= _required),
            False,
        ),
        (
            "releases_to_instruct",
            "Release work",
            "Approved, awaiting instruction",
            _release(ReleaseRequest.status == "approved", ~_instructed),
            False,
        ),
        (
            "releases_to_reconcile",
            "Release work",
            "Instructed, awaiting execution evidence",
            _release(ReleaseRequest.status == "approved", _instructed),
            False,
        ),
    ]


def visible(user):
    return [d for d in definitions(date.today()) if not d[4] or user.role != "reviewer"]


def base(ids, condition):
    return (
        select(Instrument)
        .join(Obligation, Obligation.id == Instrument.obligation_id)
        .where(Instrument.institution_id.in_(ids), condition)
    )


@router.get("/dashboard")
def dashboard(user: Actor, db: DB):
    ids = scope(db, user)
    metrics = []
    for key, group, label, condition, _ in visible(user):
        rows = base(ids, condition).subquery()
        count, amount = db.execute(
            select(func.count(), func.coalesce(func.sum(rows.c.principal_amount), 0))
        ).one()
        metrics.append(
            {
                "key": key,
                "group": group,
                "label": label,
                "grain": GRAIN,
                "count": count,
                "amount": f"{amount:.2f}",
            }
        )
    obligations = db.scalars(
        select(Obligation).where(Obligation.institution_id.in_(ids)).order_by(Obligation.title)
    ).all()
    return {
        "metrics": metrics,
        "coverage": [
            {k: v for k, v in coverage_view(db, o).items() if k != "instruments"}
            for o in obligations
        ],
    }


def drill_rows(db: Session, user, key: str, ids=None) -> tuple[str, list[dict]] | None:
    """The FDRs a metric counts, or None if the metric is not visible to this user."""
    found = next((d for d in visible(user) if d[0] == key), None)
    if not found:
        return None
    # ponytail: unpaginated drill-down; add keyset pagination when portfolios grow past ~1k rows.
    rows = db.execute(
        base(scope(db, user) if ids is None else ids, found[3])
        .add_columns(Institution.name)
        .join(Institution, Institution.id == Instrument.institution_id)
        .order_by(Instrument.maturity_date, Instrument.id)
    ).all()
    return found[2], [
        {
            "id": str(i.id),
            "bank_reference": i.bank_reference,
            "bank_name": i.bank_name,
            "institution": name,
            "principal_amount": f"{i.principal_amount:.2f}",
            "maturity_date": i.maturity_date.isoformat(),
            "status": i.status,
        }
        for i, name in rows
    ]


@router.get("/dashboard/{key}")
def drill(key: str, user: Actor, db: DB):
    result = drill_rows(db, user, key)
    if not result:
        raise Problem(404, "not_found", "Unknown metric.")
    label, items = result
    return {"key": key, "label": label, "grain": GRAIN, "items": items}
