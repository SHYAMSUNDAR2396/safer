"""Versioned policies: what rules apply to an obligation on a given date.

A draft is published by a different administrator and is then immutable; a change is a new
version. Resolution picks the published version in force on the date, preferring one written
for the obligation's kind over a general ('*') one. Decisions copy `snapshot(policy)` so they
keep the exact rules they relied on. Demo policies are illustrative: `owner_validated` is set
only by the organisation's policy owner, which is a governance step outside this prototype.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from safer.authority import Admin, EmptyInput
from safer.errors import Problem
from safer.models import AuditEvent, Obligation, Policy, User
from safer.security import DB, Actor

router = APIRouter(prefix="/api/v1")
Clearance = Literal[
    "no_dues_certificate", "closure_approval_letter", "bank_lien_release", "audit_confirmation"
]


class ReleaseRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clearances: Annotated[list[Clearance], Field(min_length=1)]
    release_not_before: Literal["obligation_end", "any_time"]

    @field_validator("clearances")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Each clearance may appear once")
        return value


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Literal["release"]
    applies_to: Annotated[str, StringConstraints(pattern=r"^(\*|[a-z_]{3,50})$")]
    effective_from: date
    effective_until: date | None = None
    rules: ReleaseRules
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


def resolve(db: Session, code: str, obligation: Obligation, on: date) -> Policy | None:
    return db.scalar(
        select(Policy)
        .where(
            Policy.code == code,
            Policy.status == "published",
            Policy.applies_to.in_((obligation.kind, "*")),
            Policy.effective_from <= on,
            or_(Policy.effective_until.is_(None), Policy.effective_until > on),
        )
        .order_by(case((Policy.applies_to == "*", 1), else_=0), Policy.version.desc())
        .limit(1)
    )


def snapshot(policy: Policy) -> dict:
    return {
        "policy_id": str(policy.id),
        "code": policy.code,
        "version": policy.version,
        "rules": policy.rules,
        "owner_validated": policy.owner_validated,
    }


def policy_view(db: Session, p: Policy) -> dict:
    names = dict(
        db.execute(
            select(User.id, User.display_name).where(User.id.in_([p.drafted_by, p.published_by]))
        ).all()
    )
    return snapshot(p) | {
        "id": str(p.id),
        "applies_to": p.applies_to,
        "effective_from": p.effective_from.isoformat(),
        "effective_until": p.effective_until.isoformat() if p.effective_until else None,
        "note": p.note,
        "status": p.status,
        "drafted_by": names[p.drafted_by],
        "published_by": names.get(p.published_by),
        "published_at": p.published_at.isoformat() if p.published_at else None,
    }


def record(db: Session, request: Request, user: User, action: str, p: Policy):
    db.add(
        AuditEvent(
            institution_id=user.institution_id,
            actor_id=user.id,
            action=action,
            request_id=request.state.request_id,
            detail={"policy_id": str(p.id), "code": p.code, "version": p.version},
        )
    )


@router.get("/admin/policies")
def all_policies(user: Admin, db: DB):
    rows = db.scalars(select(Policy).order_by(Policy.code, Policy.version.desc())).all()
    return {"items": [policy_view(db, p) for p in rows]}


@router.post("/admin/policies", status_code=201)
def draft(data: PolicyInput, request: Request, user: Admin, db: DB):
    if data.effective_until and data.effective_until <= data.effective_from:
        raise Problem(422, "invalid_dates", "A version must end after it starts.")
    # ponytail: version numbering races are caught by the unique constraint (retry the request).
    version = (db.scalar(select(func.max(Policy.version)).where(Policy.code == data.code)) or 0) + 1
    p = Policy(
        **data.model_dump(exclude={"rules"}),
        rules=data.rules.model_dump(),
        version=version,
        drafted_by=user.id,
    )
    db.add(p)
    db.flush()
    record(db, request, user, "policy.drafted", p)
    db.commit()
    return policy_view(db, p)


@router.post("/admin/policies/{id}/publish")
def publish(id: UUID, data: EmptyInput, request: Request, user: Admin, db: DB):
    p = db.scalar(
        select(Policy)
        .where(Policy.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not p:
        raise Problem(404, "not_found", "Policy not found.")
    if p.status != "draft":
        raise Problem(409, "already_published", "This version is already published.")
    if p.drafted_by == user.id:
        raise Problem(403, "second_person", "A different administrator must publish this.")
    p.status, p.published_by, p.published_at = "published", user.id, datetime.now(UTC)
    record(db, request, user, "policy.published", p)
    db.commit()
    return policy_view(db, p)


@router.get("/obligations/{id}/policy")
def applicable(id: UUID, user: Actor, db: DB, on: date | None = None):
    obligation = db.scalar(
        select(Obligation).where(
            Obligation.id == id, Obligation.institution_id == user.institution_id
        )
    )
    if not obligation:
        raise Problem(404, "not_found", "Obligation not found.")
    p = resolve(db, "release", obligation, on or date.today())
    if not p:
        raise Problem(404, "no_policy", "No published release policy applies on that date.")
    return policy_view(db, p)
