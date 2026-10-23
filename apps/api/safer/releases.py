"""Release lifecycle: request -> clearances -> competent decision.

A request copies the release policy in force. Reviewers (review authority) record each required
clearance and may hold, resume, return or reopen. Only a holder of release authority who did not
record a clearance on the request may decide. Every decision names the `basis` the approver saw:
a fingerprint of everything material to the case. A stale basis is refused; a material change
after approval voids that approval until the case is reopened and decided again.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from safer import policies
from safer.authority import active
from safer.documents import instrument_documents
from safer.errors import Problem
from safer.instruments import scoped_instrument
from safer.models import (
    Grant,
    Instrument,
    Obligation,
    ReleaseClearance,
    ReleaseEvent,
    ReleaseRequest,
    ReplacementLink,
    Submission,
    User,
)
from safer.reviews import case_evidence, comparison, discrepancy_views
from safer.security import DB, Actor, Reviewer, Writer, audit

router = APIRouter(prefix="/api/v1")
LIVE = ("open", "on_hold", "returned", "approved")
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class RequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Note


class NoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: Note


class ClearanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clearance: policies.Clearance
    note: Note


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: Annotated[bool, Field(strict=True)]
    note: Note
    basis: Annotated[str, StringConstraints(max_length=64)]


def holds(db: Session, user: User, authority: str, institution_id) -> bool:
    return bool(
        db.scalar(
            select(Grant.id).where(
                Grant.user_id == user.id,
                Grant.institution_id == institution_id,
                active(authority),
            )
        )
    )


def basis(db: Session, req: ReleaseRequest, item: Instrument) -> str:
    """Fingerprint of everything material to the decision on this request."""
    docs, states, current = instrument_documents(db, item)
    links = db.scalars(
        select(ReplacementLink).where(
            or_(
                ReplacementLink.predecessor_id == item.id,
                ReplacementLink.successor_id == item.id,
            )
        )
    ).all()
    material = {
        "instrument": [item.status, item.row_version],
        "submission": str(
            db.scalar(select(Submission.id).where(Submission.instrument_id == item.id))
        ),
        "evidence": sorted(str(e.id) for e in case_evidence(db, [item.id])),
        "observations": sorted([d["id"], d["status"]] for d in discrepancy_views(db, [item.id])),
        "replacement": sorted([str(link.id), link.status] for link in links),
        "documents": sorted([str(d.id), states[d.id] or ""] for d in docs if d.id in current),
        "clearances": sorted(
            db.scalars(
                select(ReleaseClearance.clearance).where(ReleaseClearance.request_id == req.id)
            )
        ),
        "policy": [req.policy_snapshot["policy_id"], req.policy_snapshot["version"]],
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()


def eligibility(db: Session, item: Instrument, rules: dict) -> str | None:
    """None if releasable under these rules, else the reason it is not."""
    if rules["release_not_before"] == "any_time":
        return None
    ended = db.get(Obligation, item.obligation_id).required_until
    if ended and ended <= date.today():
        return None
    replaced = db.scalar(
        select(ReplacementLink.id).where(
            ReplacementLink.predecessor_id == item.id, ReplacementLink.status == "accepted"
        )
    )
    if replaced:
        return None
    return "Cover is still required: the obligation is ongoing and no replacement was accepted."


def request_view(db: Session, req: ReleaseRequest) -> dict:
    item = db.get(Instrument, req.instrument_id)
    clearances = db.scalars(
        select(ReleaseClearance)
        .where(ReleaseClearance.request_id == req.id)
        .order_by(ReleaseClearance.created_at)
    ).all()
    events = db.scalars(
        select(ReleaseEvent)
        .where(ReleaseEvent.request_id == req.id)
        .order_by(ReleaseEvent.created_at, ReleaseEvent.id)
    ).all()
    ids = (
        {req.requested_by, req.decided_by}
        | {c.cleared_by for c in clearances}
        | {e.actor_id for e in events}
    )
    names = dict(
        db.execute(select(User.id, User.display_name).where(User.id.in_(ids - {None}))).all()
    )
    current = basis(db, req, item)
    valid = req.status == "approved" and req.decision_basis == current
    required = req.policy_snapshot["rules"]["clearances"]
    done = {c.clearance for c in clearances}
    return {
        "id": str(req.id),
        "instrument_id": str(req.instrument_id),
        "bank_reference": item.bank_reference,
        "status": req.status,
        "effective_status": "approval_invalidated"
        if req.status == "approved" and not valid
        else req.status,
        "approval_valid": valid,
        "reason": req.reason,
        "requested_by": names[req.requested_by],
        "created_at": req.created_at.isoformat(),
        "policy": req.policy_snapshot,
        "clearances": [
            {
                "clearance": c,
                "done": c in done,
                "cleared_by": next(
                    (names[x.cleared_by] for x in clearances if x.clearance == c), None
                ),
            }
            for c in required
        ],
        "ready_for_decision": req.status == "open" and done >= set(required),
        "decided_by": names.get(req.decided_by),
        "decided_at": req.decided_at.isoformat() if req.decided_at else None,
        "decision_note": req.decision_note,
        "basis": current,
        "events": [
            {
                "kind": e.kind,
                "actor": names[e.actor_id],
                "note": e.note,
                "created_at": e.created_at.isoformat(),
            }
            for e in events
        ],
    }


def locked(db: Session, id: UUID) -> ReleaseRequest:
    req = db.scalar(
        select(ReleaseRequest)
        .where(ReleaseRequest.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not req:
        raise Problem(404, "not_found", "Release request not found.")
    return req


def step(db, request, user, req, kind: str, note: str, status: str | None = None, value=None):
    if status:
        req.status = status
    db.add(ReleaseEvent(request_id=req.id, kind=kind, actor_id=user.id, note=note, basis=value))
    audit(
        db,
        request,
        user,
        f"release.{kind}",
        db.get(Instrument, req.instrument_id),
        {"request_id": str(req.id)},
    )
    db.commit()
    return request_view(db, req)


def as_reviewer(db: Session, user: User, id: UUID) -> ReleaseRequest:
    req = locked(db, id)
    if not holds(db, user, "review", req.institution_id):
        raise Problem(404, "not_found", "Release request not found.")
    return req


def as_institution(db: Session, user: User, id: UUID) -> ReleaseRequest:
    req = locked(db, id)
    if req.institution_id != user.institution_id:
        raise Problem(404, "not_found", "Release request not found.")
    return req


def expect(req: ReleaseRequest, *statuses: str):
    if req.status not in statuses:
        raise Problem(409, "invalid_transition", f"Not possible while the request is {req.status}.")


@router.post("/instruments/{id}/release-requests", status_code=201)
def create(id: UUID, data: RequestInput, request: Request, user: Writer, db: DB):
    item = scoped_instrument(db, user, id, lock=True)
    if item.status != "submitted":
        raise Problem(409, "not_submitted", "Only submitted FDRs can be released.")
    policy = policies.resolve(db, "release", db.get(Obligation, item.obligation_id), date.today())
    if not policy:
        raise Problem(409, "no_policy", "No published release policy applies today.")
    if reason := eligibility(db, item, policy.rules):
        raise Problem(409, "not_eligible", reason)
    req = ReleaseRequest(
        instrument_id=item.id,
        institution_id=item.institution_id,
        requested_by=user.id,
        reason=data.reason,
        policy_snapshot=policies.snapshot(policy),
    )
    db.add(req)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Problem(409, "already_requested", "A release request for this FDR is already live.")
    return step(db, request, user, req, "requested", data.reason)


@router.get("/instruments/{id}/release-requests")
def for_instrument(id: UUID, user: Actor, db: DB):
    scoped_instrument(db, user, id)
    rows = db.scalars(
        select(ReleaseRequest)
        .where(ReleaseRequest.instrument_id == id)
        .order_by(ReleaseRequest.created_at)
    ).all()
    return {"items": [request_view(db, r) for r in rows]}


@router.get("/release-requests/{id}")
def read(id: UUID, user: Actor, db: DB):
    req = db.get(ReleaseRequest, id)
    allowed = req and (
        req.institution_id == user.institution_id
        if user.role in ("institution_user", "auditor")
        else holds(db, user, "review", req.institution_id)
        or holds(db, user, "release_approve", req.institution_id)
    )
    if not allowed:
        raise Problem(404, "not_found", "Release request not found.")
    return request_view(db, req)


@router.get("/releases/pending")
def pending_decisions(user: Reviewer, db: DB):
    rows = db.scalars(
        select(ReleaseRequest)
        .join(Grant, Grant.institution_id == ReleaseRequest.institution_id)
        .where(
            Grant.user_id == user.id,
            active("release_approve"),
            ReleaseRequest.status.in_(("open",)),
        )
        .order_by(ReleaseRequest.created_at)
        .limit(100)
    ).all()
    return {"items": [request_view(db, r) for r in rows]}


@router.post("/release-requests/{id}/withdraw")
def withdraw(id: UUID, data: NoteInput, request: Request, user: Writer, db: DB):
    req = as_institution(db, user, id)
    expect(req, "open", "on_hold", "returned")
    return step(db, request, user, req, "withdrawn", data.note, "withdrawn")


@router.post("/release-requests/{id}/resubmit")
def resubmit(id: UUID, data: NoteInput, request: Request, user: Writer, db: DB):
    req = as_institution(db, user, id)
    expect(req, "returned")
    return step(db, request, user, req, "resubmitted", data.note, "open")


@router.post("/release-requests/{id}/clearances", status_code=201)
def clear(id: UUID, data: ClearanceInput, request: Request, user: Reviewer, db: DB):
    req = as_reviewer(db, user, id)
    expect(req, "open", "on_hold")
    if data.clearance not in req.policy_snapshot["rules"]["clearances"]:
        raise Problem(422, "not_required", "The applicable policy does not require that clearance.")
    db.add(
        ReleaseClearance(
            request_id=req.id, clearance=data.clearance, cleared_by=user.id, note=data.note
        )
    )
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Problem(409, "already_cleared", "That clearance is already recorded.")
    return step(db, request, user, req, "cleared", f"{data.clearance}: {data.note}")


@router.post("/release-requests/{id}/hold")
def hold(id: UUID, data: NoteInput, request: Request, user: Reviewer, db: DB):
    req = as_reviewer(db, user, id)
    expect(req, "open")
    return step(db, request, user, req, "held", data.note, "on_hold")


@router.post("/release-requests/{id}/resume")
def resume(id: UUID, data: NoteInput, request: Request, user: Reviewer, db: DB):
    req = as_reviewer(db, user, id)
    expect(req, "on_hold")
    return step(db, request, user, req, "resumed", data.note, "open")


@router.post("/release-requests/{id}/return")
def send_back(id: UUID, data: NoteInput, request: Request, user: Reviewer, db: DB):
    req = as_reviewer(db, user, id)
    expect(req, "open", "on_hold")
    return step(db, request, user, req, "returned", data.note, "returned")


@router.post("/release-requests/{id}/reopen")
def reopen(id: UUID, data: NoteInput, request: Request, user: Reviewer, db: DB):
    req = as_reviewer(db, user, id)
    expect(req, "approved")
    if req.decision_basis == basis(db, req, db.get(Instrument, req.instrument_id)):
        raise Problem(409, "approval_still_valid", "Nothing material changed since approval.")
    return step(db, request, user, req, "reopened", data.note, "open")


@router.post("/release-requests/{id}/decision")
def decide(
    id: UUID,
    data: DecisionInput,
    request: Request,
    user: Reviewer,
    db: DB,
    idempotency_key: Annotated[
        str, Header(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$")
    ],
):
    req = locked(db, id)
    if not holds(db, user, "release_approve", req.institution_id):
        raise Problem(404, "not_found", "Release request not found.")
    if req.status in ("approved", "rejected"):
        if req.decided_by == user.id and req.decision_key == idempotency_key:
            return request_view(db, req)  # replay of the same decision
        raise Problem(409, "already_decided", "This request has already been decided.")
    expect(req, "open")
    item = scoped_instrument_for_update(db, req.instrument_id)
    clearers = set(
        db.scalars(select(ReleaseClearance.cleared_by).where(ReleaseClearance.request_id == req.id))
    )
    if user.id in clearers:
        raise Problem(403, "separation_of_duties", "Whoever recorded a clearance cannot decide.")
    if data.approve:
        required = set(req.policy_snapshot["rules"]["clearances"])
        done = set(
            db.scalars(
                select(ReleaseClearance.clearance).where(ReleaseClearance.request_id == req.id)
            )
        )
        if not required <= done:
            raise Problem(
                409, "clearances_pending", "Every required clearance must be recorded first."
            )
        sub = db.scalar(select(Submission).where(Submission.instrument_id == item.id))
        rows = comparison(sub.snapshot, case_evidence(db, [item.id]))
        if any(r["status"] == "mismatch" for r in rows):
            raise Problem(
                409, "evidence_mismatch", "Recorded evidence contradicts the submitted claim."
            )
        if any(d["status"] == "open" for d in discrepancy_views(db, [item.id])):
            raise Problem(409, "open_observations", "Resolve open observations first.")
    current = basis(db, req, item)
    if data.basis != current:
        raise Problem(412, "stale_basis", "The case changed since you loaded it. Review it again.")
    req.status = "approved" if data.approve else "rejected"
    req.decided_by, req.decided_at, req.decision_note = user.id, datetime.now(UTC), data.note
    req.decision_basis, req.decision_key = current, idempotency_key
    return step(db, request, user, req, req.status, data.note, value=current)


def scoped_instrument_for_update(db: Session, id) -> Instrument:
    return db.scalar(
        select(Instrument)
        .where(Instrument.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
