"""Scoped authority: who may act for which institution, until when, approved by whom.

Rules enforced here and backed by database constraints:
- admins manage grants but never hold case authority, and never grant to themselves;
- only reviewers hold authority, never over their own organisation;
- 'release_approve' is sensitive: a second admin must approve it (dual control);
- delegation never outlives its source, cannot be delegated again, and ends with its source.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from safer.errors import Problem
from safer.models import AuditEvent, Grant, Institution, User
from safer.security import DB, Actor, Reviewer

router = APIRouter(prefix="/api/v1")
SENSITIVE = {"release_approve"}
MAX_TERM = timedelta(days=366)
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=300)]


def active(authority: str | None = None):
    """SQL condition for a grant currently in force (optionally for one authority)."""
    condition = and_(
        Grant.status == "active",
        Grant.valid_from <= func.now(),
        or_(Grant.valid_until.is_(None), Grant.valid_until > func.now()),
    )
    return and_(condition, Grant.authority == authority) if authority else condition


def admin(user: Actor) -> User:
    if user.role != "admin":
        raise Problem(403, "admins_only", "Only access administrators can manage authority.")
    return user


Admin = Annotated[User, Depends(admin)]


class GrantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    authority: Literal["review", "release_approve"]
    institution_id: UUID
    valid_until: AwareDatetime
    reason: Reason


class DelegationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    valid_until: AwareDatetime
    reason: Reason


class RevokeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


def record(db: Session, request: Request, actor: User, action: str, grant: Grant):
    db.add(
        AuditEvent(
            institution_id=grant.institution_id,
            actor_id=actor.id,
            action=action,
            request_id=request.state.request_id,
            detail={
                "grant_id": str(grant.id),
                "user_id": str(grant.user_id),
                "authority": grant.authority,
            },
        )
    )


def grant_view(db: Session, g: Grant) -> dict:
    ids = {g.user_id, g.requested_by, g.approved_by, g.revoked_by} - {None}
    names = dict(db.execute(select(User.id, User.display_name).where(User.id.in_(ids))).all())
    institution = db.get(Institution, g.institution_id)
    now = db.scalar(select(func.now()))
    return {
        "id": str(g.id),
        "user_id": str(g.user_id),
        "user": names[g.user_id],
        "authority": g.authority,
        "institution": {"id": str(institution.id), "name": institution.name},
        "status": g.status,
        "effective": g.status == "active"
        and g.valid_from <= now
        and (g.valid_until is None or g.valid_until > now),
        "valid_from": g.valid_from.isoformat(),
        "valid_until": g.valid_until.isoformat() if g.valid_until else None,
        "requested_by": names.get(g.requested_by),
        "approved_by": names.get(g.approved_by),
        "delegated_from": str(g.delegated_from) if g.delegated_from else None,
        "reason": g.reason,
        "created_at": g.created_at.isoformat(),
        "revoked_by": names.get(g.revoked_by),
        "revoke_reason": g.revoke_reason,
    }


def check_grantee(db: Session, actor: User, user_id: UUID, institution_id: UUID) -> User:
    grantee = db.scalar(select(User).where(User.id == user_id, User.active.is_(True)))
    if not grantee:
        raise Problem(422, "invalid_grantee", "Choose an active user.")
    if grantee.id == actor.id:
        raise Problem(422, "self_grant", "Nobody can grant or delegate authority to themselves.")
    if grantee.role != "reviewer":
        raise Problem(422, "role_conflict", "Only reviewers can hold case authority.")
    if grantee.institution_id == institution_id:
        raise Problem(422, "conflict_of_interest", "No authority over your own organisation.")
    if not db.get(Institution, institution_id):
        raise Problem(422, "invalid_scope", "Choose an existing institution.")
    return grantee


def check_term(db: Session, until: datetime, ceiling: datetime | None = None):
    now = db.scalar(select(func.now()))
    if until <= now or until > now + MAX_TERM:
        raise Problem(422, "invalid_term", "Authority must end in the future, within a year.")
    if ceiling and until > ceiling:
        raise Problem(
            422, "invalid_term", "A delegation cannot outlive the authority it comes from."
        )


def insert_grant(db: Session, grant: Grant) -> Grant:
    # Expired-but-active rows would otherwise block a fresh grant on the same scope.
    db.execute(
        update(Grant)
        .where(
            Grant.user_id == grant.user_id,
            Grant.authority == grant.authority,
            Grant.institution_id == grant.institution_id,
            Grant.status == "active",
            Grant.valid_until <= func.now(),
        )
        .values(status="expired")
    )
    db.add(grant)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Problem(409, "already_granted", "This person already has or awaits that authority.")
    return grant


def end(db: Session, actor: User, grant: Grant, reason: str):
    """Revoke an active grant (or reject a pending one) and everything delegated from it."""
    now = datetime.now(UTC)
    for g in [grant, *db.scalars(select(Grant).where(Grant.delegated_from == grant.id))]:
        if g.status == "active":
            g.status, g.revoked_at, g.revoked_by, g.revoke_reason = "revoked", now, actor.id, reason
        elif g.status == "pending":
            g.status, g.decided_at, g.revoke_reason = "rejected", now, reason


@router.get("/admin/users")
def users(user: Admin, db: DB):
    rows = db.execute(
        select(User, Institution.name)
        .join(Institution, Institution.id == User.institution_id)
        .where(User.active.is_(True))
        .order_by(User.role, User.display_name)
    ).all()
    institutions = db.execute(select(Institution.id, Institution.name).order_by(Institution.name))
    return {
        "users": [
            {"id": str(u.id), "name": u.display_name, "role": u.role, "organisation": name}
            for u, name in rows
        ],
        "institutions": [{"id": str(i), "name": n} for i, n in institutions],
    }


@router.get("/admin/grants")
def grants(user: Admin, db: DB):
    rows = db.scalars(select(Grant).order_by(Grant.created_at.desc()).limit(200)).all()
    return {"items": [grant_view(db, g) for g in rows]}


@router.post("/admin/grants", status_code=201)
def create(data: GrantInput, request: Request, user: Admin, db: DB):
    check_grantee(db, user, data.user_id, data.institution_id)
    check_term(db, data.valid_until)
    sensitive = data.authority in SENSITIVE
    g = insert_grant(
        db,
        Grant(
            **data.model_dump(),
            status="pending" if sensitive else "active",
            requested_by=user.id,
            approved_by=None if sensitive else user.id,
            decided_at=None if sensitive else datetime.now(UTC),
        ),
    )
    record(db, request, user, "grant.requested" if sensitive else "grant.activated", g)
    db.commit()
    return grant_view(db, g)


def pending(db: Session, id: UUID) -> Grant:
    g = db.scalar(
        select(Grant)
        .where(Grant.id == id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not g:
        raise Problem(404, "not_found", "Grant not found.")
    if g.status != "pending":
        raise Problem(409, "already_decided", "This grant was already decided.")
    return g


@router.post("/admin/grants/{id}/approve")
def approve(id: UUID, data: EmptyInput, request: Request, user: Admin, db: DB):
    g = pending(db, id)
    if user.id in (g.requested_by, g.user_id):
        raise Problem(403, "dual_control", "A different administrator must approve this grant.")
    g.status, g.approved_by, g.decided_at = "active", user.id, datetime.now(UTC)
    record(db, request, user, "grant.approved", g)
    db.commit()
    return grant_view(db, g)


@router.post("/admin/grants/{id}/reject")
def reject(id: UUID, data: RevokeInput, request: Request, user: Admin, db: DB):
    g = pending(db, id)
    g.status, g.decided_at, g.revoke_reason = "rejected", datetime.now(UTC), data.reason
    record(db, request, user, "grant.rejected", g)
    db.commit()
    return grant_view(db, g)


@router.post("/admin/grants/{id}/revoke")
def revoke(id: UUID, data: RevokeInput, request: Request, user: Admin, db: DB):
    g = db.scalar(select(Grant).where(Grant.id == id).with_for_update())
    if not g:
        raise Problem(404, "not_found", "Grant not found.")
    if g.status != "active":
        raise Problem(409, "not_active", "Only active grants can be revoked.")
    end(db, user, g, data.reason)
    record(db, request, user, "grant.revoked", g)
    db.commit()
    return grant_view(db, g)


@router.get("/grants/mine")
def mine(user: Actor, db: DB):
    held = db.scalars(
        select(Grant)
        .where(Grant.user_id == user.id, Grant.status.in_(("active", "pending")))
        .order_by(Grant.created_at)
    ).all()
    given = db.scalars(
        select(Grant).where(
            Grant.delegated_from.in_([g.id for g in held]), Grant.status.in_(("active", "pending"))
        )
    ).all()
    return {
        "held": [grant_view(db, g) for g in held],
        "delegated": [grant_view(db, g) for g in given],
    }


@router.post("/grants/{id}/delegate", status_code=201)
def delegate(id: UUID, data: DelegationInput, request: Request, user: Reviewer, db: DB):
    parent = db.scalar(select(Grant).where(Grant.id == id, Grant.user_id == user.id, active()))
    if not parent:
        raise Problem(404, "not_found", "You hold no such active authority.")
    if parent.delegated_from:
        raise Problem(422, "no_redelegation", "Delegated authority cannot be delegated again.")
    check_grantee(db, user, data.user_id, parent.institution_id)
    check_term(db, data.valid_until, parent.valid_until)
    sensitive = parent.authority in SENSITIVE
    g = insert_grant(
        db,
        Grant(
            user_id=data.user_id,
            authority=parent.authority,
            institution_id=parent.institution_id,
            valid_until=data.valid_until,
            reason=data.reason,
            delegated_from=parent.id,
            status="pending" if sensitive else "active",
            requested_by=user.id,
            approved_by=None if sensitive else user.id,
            decided_at=None if sensitive else datetime.now(UTC),
        ),
    )
    record(db, request, user, "grant.delegated", g)
    db.commit()
    return grant_view(db, g)


@router.post("/grants/{id}/revoke")
def revoke_delegation(id: UUID, data: RevokeInput, request: Request, user: Reviewer, db: DB):
    g = db.scalar(select(Grant).where(Grant.id == id).with_for_update())
    parent = db.get(Grant, g.delegated_from) if g and g.delegated_from else None
    if not parent or parent.user_id != user.id:
        raise Problem(404, "not_found", "You delegated no such authority.")
    if g.status not in ("active", "pending"):
        raise Problem(409, "not_active", "This delegation has already ended.")
    end(db, user, g, data.reason)
    record(db, request, user, "grant.revoked", g)
    db.commit()
    return grant_view(db, g)


@router.get("/grants/delegates")
def delegates(user: Reviewer, db: DB):
    rows = db.scalars(
        select(User)
        .where(User.role == "reviewer", User.active.is_(True), User.id != user.id)
        .order_by(User.display_name)
    )
    return {"items": [{"id": str(u.id), "name": u.display_name} for u in rows]}
