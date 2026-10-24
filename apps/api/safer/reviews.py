from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import select

from safer.authority import active
from safer.deadlines import deadline_view
from safer.documents import document_view, instrument_documents
from safer.errors import Problem
from safer.extraction import proposed_values
from safer.instruments import assigned_case, audit_items, scoped_instrument
from safer.models import (
    BankRequest,
    BankResponse,
    Discrepancy,
    DiscrepancyReply,
    EvidenceRecord,
    Grant,
    Institution,
    Instrument,
    Obligation,
    ReleaseRequest,
    Reminder,
    Submission,
    User,
)
from safer.replacements import coverage_view, replacement_view
from safer.schemas import DiscrepancyInput, EvidenceInput, ReplyInput
from safer.security import DB, Actor, Reviewer, audit

router = APIRouter(prefix="/api/v1")
FIELDS = {
    "bank_name": "Bank name",
    "bank_reference": "FDR reference",
    "principal_amount": "Principal amount",
    "issue_date": "Issue date",
    "maturity_date": "Maturity date",
}


def same(field: str, claimed: str, confirmed: str) -> bool:
    if field == "principal_amount":
        return Decimal(claimed) == Decimal(confirmed)
    if field == "bank_name":
        return " ".join(claimed.split()).casefold() == " ".join(confirmed.split()).casefold()
    return claimed == confirmed  # references keep leading zeros and exact characters


def comparison(snapshot: dict, records, extracted: dict | None = None) -> list[dict]:
    """Claim vs latest independent evidence per field; code decides, never a model.

    `extracted` values come from the institution's own document: shown for comparison only."""
    extracted = extracted or {}
    latest = {r.field: r for r in sorted(records, key=lambda r: (r.created_at, r.id))}
    rows = []
    for field, label in FIELDS.items():
        record, claimed = latest.get(field), str(snapshot[field])
        status = "unconfirmed"
        if record:
            status = "match" if same(field, claimed, record.value) else "mismatch"
        rows.append(
            {
                "field": field,
                "label": label,
                "claimed": claimed,
                "confirmed": record.value if record else None,
                "status": status,
                "simulated": bool(record and record.method == "bank_simulator"),
                "extracted": extracted.get(field),
                "extracted_differs": field in extracted
                and not same(field, claimed, extracted[field]),
                "evidence_id": str(record.id) if record else None,
            }
        )
    return rows


def names(db, ids) -> dict:
    return dict(db.execute(select(User.id, User.display_name).where(User.id.in_(ids))).all())


def evidence_views(db, records) -> list[dict]:
    who = names(db, {r.observer_id for r in records})
    return [
        {
            "id": str(r.id),
            "field": r.field,
            "label": FIELDS[r.field],
            "value": r.value,
            "source": r.source,
            "method": r.method,
            "observer": who[r.observer_id],
            "observed_at": r.observed_at.isoformat(),
            "note": r.note,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


def discrepancy_views(db, instrument_ids) -> list[dict]:
    items = db.scalars(
        select(Discrepancy)
        .where(Discrepancy.instrument_id.in_(instrument_ids))
        .order_by(Discrepancy.created_at, Discrepancy.id)
    ).all()
    replies = db.scalars(
        select(DiscrepancyReply)
        .where(DiscrepancyReply.discrepancy_id.in_([d.id for d in items]))
        .order_by(DiscrepancyReply.created_at, DiscrepancyReply.id)
    ).all()
    who = names(db, {d.raised_by for d in items} | {r.author_id for r in replies})
    views = []
    for d in items:
        thread = [r for r in replies if r.discrepancy_id == d.id]
        views.append(
            {
                "id": str(d.id),
                "instrument_id": str(d.instrument_id),
                "field": d.field,
                "label": FIELDS.get(d.field, "General"),
                "message": d.message,
                "raised_by": who[d.raised_by],
                "created_at": d.created_at.isoformat(),
                "status": "resolved" if any(r.kind == "resolution" for r in thread) else "open",
                "replies": [
                    {
                        "id": str(r.id),
                        "kind": r.kind,
                        "author": who[r.author_id],
                        "message": r.message,
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in thread
                ],
            }
        )
    return views


def bank_views(db, instrument_id) -> list[dict]:
    rows = db.execute(
        select(BankRequest, BankResponse)
        .outerjoin(BankResponse, BankResponse.request_id == BankRequest.id)
        .where(BankRequest.instrument_id == instrument_id)
        .order_by(BankRequest.created_at, BankRequest.id)
    ).all()
    return [
        {
            "id": str(req.id),
            "provider": req.provider,
            "simulated": req.provider == "simulator",
            "outcome": res.outcome if res else "pending",
            "detail": res.detail if res else "",
            "requested_at": req.created_at.isoformat(),
            "answered_at": res.received_at.isoformat() if res else None,
        }
        for req, res in rows
    ]


def case_evidence(db, ids):
    return db.scalars(
        select(EvidenceRecord)
        .where(EvidenceRecord.instrument_id.in_(ids))
        .order_by(EvidenceRecord.created_at, EvidenceRecord.id)
    ).all()


@router.get("/reviews")
def queue(user: Reviewer, db: DB):
    # ponytail: oldest 200 waiting cases only; add keyset pagination with the dashboard (SAF-021).
    rows = db.execute(
        select(Instrument, Institution, Submission)
        .join(Grant, Grant.institution_id == Instrument.institution_id)
        .join(Institution, Institution.id == Instrument.institution_id)
        .join(Submission, Submission.instrument_id == Instrument.id)
        .where(Grant.user_id == user.id, active("review"), Instrument.status == "submitted")
        .order_by(Submission.created_at, Instrument.id)
        .limit(200)
    ).all()
    ids = [item.id for item, _, _ in rows]
    records, threads = case_evidence(db, ids), discrepancy_views(db, ids)
    escalated = set(
        db.scalars(
            select(Reminder.instrument_id).where(
                Reminder.instrument_id.in_(ids), Reminder.kind == "escalation"
            )
        )
    )
    items = []
    for item, inst, sub in rows:
        rows_ = comparison(sub.snapshot, [r for r in records if r.instrument_id == item.id])
        statuses = [row["status"] for row in rows_ if not row["simulated"]]
        items.append(
            {
                "instrument_id": str(item.id),
                "institution": {"id": str(inst.id), "name": inst.name},
                "bank_name": sub.snapshot["bank_name"],
                "bank_reference": sub.snapshot["bank_reference"],
                "principal_amount": sub.snapshot["principal_amount"],
                "maturity_date": sub.snapshot["maturity_date"],
                "submitted_at": sub.created_at.isoformat(),
                "confirmed_fields": statuses.count("match"),
                "mismatched_fields": statuses.count("mismatch"),
                # Simulator answers are shown apart and never count as confirmation.
                "simulated_fields": sum(row["simulated"] for row in rows_),
                "escalated": item.id in escalated,
                "open_discrepancies": sum(
                    t["status"] == "open" for t in threads if t["instrument_id"] == str(item.id)
                ),
            }
        )
    return {"items": items}


def release_views(db, item) -> list[dict]:
    from safer.releases import request_view  # releases builds on this module

    rows = db.scalars(
        select(ReleaseRequest)
        .where(ReleaseRequest.instrument_id == item.id)
        .order_by(ReleaseRequest.created_at)
    ).all()
    return [request_view(db, r) for r in rows]


@router.get("/reviews/{id}")
def case(id: UUID, user: Reviewer, db: DB):
    item = assigned_case(db, user, id, closed=True)
    sub = db.scalar(select(Submission).where(Submission.instrument_id == id))
    institution = db.get(Institution, item.institution_id)
    records = case_evidence(db, [id])
    docs, states, current = instrument_documents(db, item)
    return {
        "instrument_id": str(id),
        "status": item.status,
        "institution": {"id": str(institution.id), "name": institution.name},
        "submitted_at": sub.created_at.isoformat(),
        "claim": {field: sub.snapshot[field] for field in FIELDS},
        "comparison": comparison(
            sub.snapshot,
            records,
            proposed_values(db, [d.id for d in docs if d.id in current and d.kind != "other"]),
        ),
        "evidence": evidence_views(db, records),
        "documents": [document_view(d, states[d.id], d.id in current) for d in docs],
        "submitted_documents": sub.snapshot.get("documents", []),
        "discrepancies": discrepancy_views(db, [id]),
        "bank_requests": bank_views(db, id),
        "deadlines": deadline_view(db, item),
        "replacement": replacement_view(db, item),
        "releases": release_views(db, item),
        "coverage": coverage_view(db, db.get(Obligation, item.obligation_id)),
        "audit": audit_items(db, item),
    }


@router.post("/reviews/{id}/evidence", status_code=201)
def record_evidence(id: UUID, data: EvidenceInput, request: Request, user: Reviewer, db: DB):
    item = assigned_case(db, user, id)
    record = EvidenceRecord(
        **data.model_dump(),
        instrument_id=id,
        institution_id=item.institution_id,
        observer_id=user.id,
    )
    db.add(record)
    db.flush()
    audit(
        db,
        request,
        user,
        "review.evidence_recorded",
        item,
        {"evidence_id": str(record.id), "field": record.field, "method": record.method},
    )
    db.commit()
    return evidence_views(db, [record])[0]


@router.post("/reviews/{id}/discrepancies", status_code=201)
def raise_discrepancy(id: UUID, data: DiscrepancyInput, request: Request, user: Reviewer, db: DB):
    item = assigned_case(db, user, id)
    d = Discrepancy(
        **data.model_dump(), instrument_id=id, institution_id=item.institution_id, raised_by=user.id
    )
    db.add(d)
    db.flush()
    audit(db, request, user, "review.discrepancy_raised", item, {"discrepancy_id": str(d.id)})
    db.commit()
    return discrepancy_views(db, [id])[-1]


@router.get("/instruments/{id}/discrepancies")
def institution_discrepancies(id: UUID, user: Actor, db: DB):
    scoped_instrument(db, user, id)
    return {"items": discrepancy_views(db, [id])}


@router.post("/discrepancies/{id}/replies", status_code=201)
def reply(id: UUID, data: ReplyInput, request: Request, user: Actor, db: DB):
    # The row lock serializes replies, so a resolution is final for everyone after it.
    d = db.scalar(select(Discrepancy).where(Discrepancy.id == id).with_for_update())
    if not d:
        raise Problem(404, "not_found", "Observation not found.")
    if user.role == "reviewer":
        item = assigned_case(db, user, d.instrument_id)
    else:
        item = scoped_instrument(db, user, d.instrument_id)
        if user.role != "institution_user":
            raise Problem(403, "read_only", "Your role permits read-only access.")
        if data.resolve:
            raise Problem(403, "reviewers_only", "Only the reviewer can resolve an observation.")
    if db.scalar(
        select(DiscrepancyReply.id).where(
            DiscrepancyReply.discrepancy_id == id, DiscrepancyReply.kind == "resolution"
        )
    ):
        raise Problem(409, "already_resolved", "This observation is already resolved.")
    kind = "resolution" if data.resolve else "response"
    db.add(DiscrepancyReply(discrepancy_id=id, author_id=user.id, kind=kind, message=data.message))
    action = "review.discrepancy_resolved" if data.resolve else "review.discrepancy_answered"
    audit(db, request, user, action, item, {"discrepancy_id": str(id)})
    db.commit()
    return next(v for v in discrepancy_views(db, [d.instrument_id]) if v["id"] == str(id))
