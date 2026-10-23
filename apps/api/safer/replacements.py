"""Replacement links and obligation coverage.

A proposed successor is not coverage: it is reported apart until a reviewer accepts it, and
then the predecessor stops counting, so no deposit is counted twice. Links are 1:1 (split or
partial replacement is deferred). Decisions lock the obligation row, serializing every change
to that obligation's coverage.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from safer.errors import Problem
from safer.instruments import assigned_case, scoped_instrument
from safer.models import Instrument, Obligation, ReplacementLink, User
from safer.security import DB, Actor, Reviewer, Writer, audit

router = APIRouter(prefix="/api/v1")
LIVE = ("proposed", "accepted")


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    successor_id: UUID


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accept: Annotated[bool, Field(strict=True)]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""


def live_link(db: Session, column, instrument_id) -> ReplacementLink | None:
    return db.scalar(
        select(ReplacementLink).where(column == instrument_id, ReplacementLink.status.in_(LIVE))
    )


def would_cycle(db: Session, predecessor_id, successor_id) -> bool:
    """True if the successor already leads (through live links) back to the predecessor."""
    current, seen = UUID(str(successor_id)), set()
    while current and current not in seen:
        if current == UUID(str(predecessor_id)):
            return True
        seen.add(current)
        link = live_link(db, ReplacementLink.predecessor_id, current)
        current = link.successor_id if link else None
    return False


def link_view(db: Session, link: ReplacementLink | None) -> dict | None:
    if not link:
        return None
    refs = dict(
        db.execute(
            select(Instrument.id, Instrument.bank_reference).where(
                Instrument.id.in_([link.predecessor_id, link.successor_id])
            )
        ).all()
    )
    names = dict(
        db.execute(
            select(User.id, User.display_name).where(
                User.id.in_([link.proposed_by, link.decided_by])
            )
        ).all()
    )
    return {
        "id": str(link.id),
        "predecessor_id": str(link.predecessor_id),
        "predecessor_reference": refs[link.predecessor_id],
        "successor_id": str(link.successor_id),
        "successor_reference": refs[link.successor_id],
        "status": link.status,
        "proposed_by": names[link.proposed_by],
        "proposed_at": link.proposed_at.isoformat(),
        "decided_by": names.get(link.decided_by),
        "decided_at": link.decided_at.isoformat() if link.decided_at else None,
        "decision_note": link.decision_note,
    }


def replacement_view(db: Session, item: Instrument) -> dict:
    return {
        "outgoing": link_view(db, live_link(db, ReplacementLink.predecessor_id, item.id)),
        "incoming": link_view(db, live_link(db, ReplacementLink.successor_id, item.id)),
    }


def coverage_view(db: Session, obligation: Obligation) -> dict:
    items = db.scalars(
        select(Instrument)
        .where(Instrument.obligation_id == obligation.id, Instrument.status == "submitted")
        .order_by(Instrument.created_at, Instrument.id)
    ).all()
    links = db.scalars(
        select(ReplacementLink).where(
            ReplacementLink.obligation_id == obligation.id, ReplacementLink.status.in_(LIVE)
        )
    ).all()
    superseded = {link.predecessor_id for link in links if link.status == "accepted"}
    pending = {link.successor_id for link in links if link.status == "proposed"}

    def state(item):
        if item.id in superseded:
            return "superseded"
        return "proposed_successor" if item.id in pending else "counting"

    rows = [
        {
            "id": str(i.id),
            "bank_reference": i.bank_reference,
            "principal_amount": f"{i.principal_amount:.2f}",
            "maturity_date": i.maturity_date.isoformat(),
            "state": state(i),
        }
        for i in items
    ]
    covered = sum((i.principal_amount for i in items if state(i) == "counting"), Decimal(0))
    proposed = sum((i.principal_amount for i in items if i.id in pending), Decimal(0))
    return {
        "obligation_id": str(obligation.id),
        "title": obligation.title,
        "required_amount": f"{obligation.required_amount:.2f}",
        "covered_amount": f"{covered:.2f}",
        "proposed_amount": f"{proposed:.2f}",
        "gap_amount": f"{max(obligation.required_amount - covered, Decimal(0)):.2f}",
        "basis": "Submitted claims; not independently confirmed coverage.",
        "instruments": rows,
    }


@router.post("/instruments/{id}/replacement", status_code=201)
def propose(id: UUID, data: ProposalInput, request: Request, user: Writer, db: DB):
    old = scoped_instrument(db, user, id, lock=True)
    new = scoped_instrument(db, user, data.successor_id)
    if new.id == old.id:
        raise Problem(422, "invalid_replacement", "An FDR cannot replace itself.")
    if old.status != "submitted" or new.status != "submitted":
        raise Problem(409, "not_submitted", "Both FDRs must be submitted first.")
    if new.obligation_id != old.obligation_id:
        raise Problem(422, "invalid_replacement", "The replacement must cover the same obligation.")
    if new.principal_amount < old.principal_amount:
        raise Problem(
            422, "partial_replacement", "Partial or split replacement is not supported yet."
        )
    if new.maturity_date <= old.maturity_date:
        raise Problem(422, "invalid_replacement", "The replacement must mature later.")
    if live_link(db, ReplacementLink.predecessor_id, old.id) or live_link(
        db, ReplacementLink.successor_id, new.id
    ):
        raise Problem(409, "already_linked", "One of these FDRs is already in a replacement.")
    if would_cycle(db, old.id, new.id):
        raise Problem(422, "replacement_cycle", "This would create a replacement cycle.")
    link = ReplacementLink(
        institution_id=old.institution_id,
        obligation_id=old.obligation_id,
        predecessor_id=old.id,
        successor_id=new.id,
        proposed_by=user.id,
    )
    db.add(link)
    try:
        db.flush()
    except IntegrityError:  # a concurrent proposal took one side first
        db.rollback()
        raise Problem(409, "already_linked", "One of these FDRs is already in a replacement.")
    for item in (old, new):
        audit(db, request, user, "replacement.proposed", item, {"link_id": str(link.id)})
    db.commit()
    return link_view(db, link)


@router.post("/replacements/{id}/decision")
def decide(id: UUID, data: DecisionInput, request: Request, user: Reviewer, db: DB):
    link = db.get(ReplacementLink, id)
    if not link:
        raise Problem(404, "not_found", "Replacement not found.")
    old = assigned_case(db, user, link.predecessor_id)
    # Aggregate lock: every coverage change for this obligation is serialized here.
    db.scalar(select(Obligation).where(Obligation.id == link.obligation_id).with_for_update())
    link = db.scalar(
        select(ReplacementLink)
        .where(ReplacementLink.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if link.status != "proposed":
        raise Problem(409, "already_decided", "This replacement was already decided.")
    link.status = "accepted" if data.accept else "rejected"
    link.decided_by, link.decided_at, link.decision_note = user.id, datetime.now(UTC), data.note
    new = db.get(Instrument, link.successor_id)
    for item in (old, new):
        audit(db, request, user, f"replacement.{link.status}", item, {"link_id": str(link.id)})
    db.commit()
    return link_view(db, link)


@router.get("/instruments/{id}/replacement")
def replacement(id: UUID, user: Actor, db: DB):
    item = scoped_instrument(db, user, id)
    candidates = db.scalars(
        select(Instrument)
        .where(
            Instrument.institution_id == item.institution_id,
            Instrument.obligation_id == item.obligation_id,
            Instrument.status == "submitted",
            Instrument.id != item.id,
            Instrument.maturity_date > item.maturity_date,
            Instrument.principal_amount >= item.principal_amount,
        )
        .order_by(Instrument.maturity_date)
        .limit(50)
    ).all()
    return replacement_view(db, item) | {
        "candidates": [
            {
                "id": str(c.id),
                "bank_reference": c.bank_reference,
                "maturity_date": c.maturity_date.isoformat(),
                "principal_amount": f"{c.principal_amount:.2f}",
            }
            for c in candidates
            if not live_link(db, ReplacementLink.successor_id, c.id)
        ]
    }


@router.get("/obligations/{id}/coverage")
def coverage(id: UUID, user: Actor, db: DB):
    obligation = db.scalar(
        select(Obligation).where(
            Obligation.id == id, Obligation.institution_id == user.institution_id
        )
    )
    if not obligation:
        raise Problem(404, "not_found", "Obligation not found.")
    return coverage_view(db, obligation)
