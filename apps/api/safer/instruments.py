from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response
from sqlalchemy import func, or_, select, tuple_

from safer.errors import Problem
from safer.models import (
    AuditEvent,
    Instrument,
    Obligation,
    ReviewAssignment,
    Submission,
    User,
)
from safer.schemas import DraftInput, EmptyCommand, InstrumentView
from safer.security import DB, Actor, Writer, audit

router = APIRouter(prefix="/api/v1")


def view(item: Instrument) -> InstrumentView:
    return InstrumentView(
        id=item.id,
        institution_id=item.institution_id,
        obligation_id=item.obligation_id,
        bank_name=item.bank_name,
        bank_reference=item.bank_reference,
        principal_amount=f"{item.principal_amount:.2f}",
        currency=item.currency,
        issue_date=item.issue_date,
        maturity_date=item.maturity_date,
        status=item.status,
        row_version=item.row_version,
        created_at=item.created_at,
    )


def scoped_instrument(db, user, id: UUID, lock=False):
    query = select(Instrument).where(
        Instrument.id == id, Instrument.institution_id == user.institution_id
    )
    if lock:
        # Sessions keep objects across commits; a lock must re-read the row it locks.
        query = query.with_for_update().execution_options(populate_existing=True)
    item = db.scalar(query)
    if not item:
        raise Problem(404, "not_found", "Record not found.")
    return item


def assigned_case(db, user, id: UUID):
    """A submitted instrument of an institution assigned to this reviewer, else 404."""
    item = db.scalar(
        select(Instrument)
        .join(ReviewAssignment, ReviewAssignment.institution_id == Instrument.institution_id)
        .where(
            Instrument.id == id,
            Instrument.status == "submitted",
            ReviewAssignment.reviewer_id == user.id,
        )
    )
    if not item:
        raise Problem(404, "not_found", "Case not found.")
    return item


def check_obligation(db, user, id):
    found = db.scalar(
        select(Obligation.id).where(
            Obligation.id == id, Obligation.institution_id == user.institution_id
        )
    )
    if not found:
        raise Problem(404, "not_found", "Obligation not found.")


def check_version(item, match):
    if match is None:
        raise Problem(428, "precondition_required", "A current record version is required.")
    if match != f'"{item.row_version}"':
        raise Problem(
            412,
            "stale_version",
            "This record changed in another session. Reload before continuing.",
        )


@router.get("/obligations")
def obligations(user: Actor, db: DB):
    rows = db.scalars(
        select(Obligation)
        .where(Obligation.institution_id == user.institution_id)
        .order_by(Obligation.title)
    ).all()
    return {
        "items": [
            {
                "id": str(row.id),
                "title": row.title,
                "required_amount": f"{row.required_amount:.2f}",
                "currency": row.currency,
                "required_documents": row.required_documents,
            }
            for row in rows
        ]
    }


@router.get("/instruments")
def list_instruments(
    user: Actor,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: UUID | None = None,
    q: Annotated[str, Query(max_length=100)] = "",
):
    scoped = Instrument.institution_id == user.institution_id
    query = select(Instrument).where(scoped)
    if q.strip():
        query = query.where(
            or_(
                Instrument.bank_reference.icontains(q.strip(), autoescape=True),
                Instrument.bank_name.icontains(q.strip(), autoescape=True),
            )
        )
    if cursor:
        anchor = scoped_instrument(db, user, cursor)
        query = query.where(
            tuple_(Instrument.created_at, Instrument.id) < tuple_(anchor.created_at, anchor.id)
        )
    rows = list(
        db.scalars(
            query.order_by(Instrument.created_at.desc(), Instrument.id.desc()).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    count, amount = db.execute(
        select(func.count(), func.coalesce(func.sum(Instrument.principal_amount), 0)).where(scoped)
    ).one()
    drafts = db.scalar(
        select(func.count()).select_from(Instrument).where(scoped, Instrument.status == "draft")
    )
    return {
        "items": [view(row) for row in rows],
        "next_cursor": str(rows[-1].id) if has_more else None,
        "summary": {
            "total": count,
            "drafts": drafts,
            "submitted": count - drafts,
            "recorded_amount": f"{amount:.2f}",
        },
    }


@router.post("/instruments", status_code=201, response_model=InstrumentView)
def create_instrument(data: DraftInput, request: Request, user: Writer, db: DB, response: Response):
    check_obligation(db, user, data.obligation_id)
    item = Instrument(
        **data.model_dump(exclude={"principal_amount"}),
        principal_amount=Decimal(data.principal_amount),
        institution_id=user.institution_id,
        created_by=user.id,
    )
    db.add(item)
    db.flush()
    audit(db, request, user, "instrument.created", item)
    db.commit()
    response.headers["ETag"] = f'"{item.row_version}"'
    return view(item)


@router.get("/instruments/{id}", response_model=InstrumentView)
def get_instrument(id: UUID, user: Actor, db: DB, response: Response):
    item = scoped_instrument(db, user, id)
    response.headers["ETag"] = f'"{item.row_version}"'
    return view(item)


@router.patch("/instruments/{id}", response_model=InstrumentView)
def update_instrument(
    id: UUID,
    data: DraftInput,
    request: Request,
    user: Writer,
    db: DB,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
):
    item = scoped_instrument(db, user, id, lock=True)
    if item.status != "draft":
        raise Problem(409, "already_submitted", "Submitted records are immutable in this slice.")
    check_version(item, if_match)
    check_obligation(db, user, data.obligation_id)
    for key, value in data.model_dump().items():
        setattr(item, key, Decimal(value) if key == "principal_amount" else value)
    item.row_version += 1
    audit(db, request, user, "instrument.updated", item)
    db.commit()
    response.headers["ETag"] = f'"{item.row_version}"'
    return view(item)


def submission_view(row):
    return {
        "id": str(row.id),
        "instrument_id": str(row.instrument_id),
        "snapshot": row.snapshot,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/instruments/{id}/submissions", status_code=201)
def submit(
    id: UUID,
    data: EmptyCommand,
    request: Request,
    user: Writer,
    db: DB,
    response: Response,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
    if_match: Annotated[str | None, Header()] = None,
):
    item = scoped_instrument(db, user, id, lock=True)
    previous = db.scalar(select(Submission).where(Submission.instrument_id == id))
    if previous:
        if previous.actor_id == user.id and previous.idempotency_key == idempotency_key:
            response.status_code = 200
            return submission_view(previous)
        raise Problem(409, "already_submitted", "This record has already been submitted.")
    check_version(item, if_match)
    if item.status != "draft":
        raise Problem(409, "invalid_transition", "Only drafts may be submitted.")
    from safer.documents import submission_documents  # documents imports this module

    documents = submission_documents(db, item)
    item.status = "submitted"
    item.row_version += 1
    row = Submission(
        instrument_id=id,
        actor_id=user.id,
        idempotency_key=idempotency_key,
        snapshot=view(item).model_dump(mode="json") | {"documents": documents},
    )
    db.add(row)
    audit(db, request, user, "instrument.submitted", item)
    db.commit()
    return submission_view(row)


@router.get("/instruments/{id}/audit")
def timeline(id: UUID, user: Actor, db: DB):
    item = scoped_instrument(db, user, id)
    return {"items": audit_items(db, item)}


def audit_items(db, item) -> list[dict]:
    rows = db.execute(
        select(AuditEvent, User.display_name)
        .outerjoin(User, User.id == AuditEvent.actor_id)
        .where(
            AuditEvent.instrument_id == item.id, AuditEvent.institution_id == item.institution_id
        )
        .order_by(AuditEvent.created_at, AuditEvent.id)
    ).all()
    return [
        {
            "id": str(e.id),
            "action": e.action,
            "actor": name or "SAFER malware scanner",
            "row_version": e.row_version,
            "created_at": e.created_at.isoformat(),
            "request_id": e.request_id,
        }
        for e, name in rows
    ]
