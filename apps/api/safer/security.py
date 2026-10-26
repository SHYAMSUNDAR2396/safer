import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from safer.db import get_db
from safer.errors import Problem
from safer.models import AuditEvent, SessionRow, User

DB = Annotated[Session, Depends(get_db)]


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(db: Session, user: User, *, mfa_verified: bool = False) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    db.add(
        SessionRow(
            token_hash=token_hash(token),
            user_id=user.id,
            csrf_token=csrf,
            mfa_verified=mfa_verified,
            created_at=now,
            last_seen_at=now,
        )
    )
    return token, csrf


def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get("safer_session")
    if not token or len(token) > 128:
        raise Problem(401, "authentication_required", "Sign in to continue.")
    row = db.get(SessionRow, token_hash(token))
    now = datetime.now(UTC)
    if (
        not row
        or now - row.created_at >= timedelta(hours=8)
        or now - row.last_seen_at >= timedelta(minutes=30)
    ):
        raise Problem(401, "authentication_required", "Your session has expired. Sign in again.")
    user = db.scalar(select(User).where(User.id == row.user_id, User.active.is_(True)))
    if not user:
        raise Problem(401, "authentication_required", "This account no longer has access.")
    if user.role in {"reviewer", "admin"} and not row.mfa_verified:
        raise Problem(
            401,
            "mfa_required",
            "Sign in again and complete the second factor for privileged access.",
        )
    request.state.session_hash = row.token_hash
    request.state.csrf_token = row.csrf_token
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") != request.app.state.settings.app_origin:
            raise Problem(403, "invalid_origin", "This request must originate from the portal.")
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), row.csrf_token):
            raise Problem(403, "csrf_failed", "Refresh the page and try again.")
    row.last_seen_at = now
    db.commit()
    return user


Actor = Annotated[User, Depends(current_user)]


def writer(user: Actor) -> User:
    if user.role != "institution_user":
        raise Problem(403, "read_only", "Your role permits read-only access.")
    return user


Writer = Annotated[User, Depends(writer)]


def reviewer(user: Actor) -> User:
    if user.role != "reviewer":
        raise Problem(403, "reviewers_only", "Only assigned reviewers can do this.")
    return user


Reviewer = Annotated[User, Depends(reviewer)]


def audit(db: Session, request: Request, actor: User, action: str, instrument=None, detail=None):
    db.add(
        AuditEvent(
            # A reviewer's actions belong to the reviewed institution's history.
            institution_id=instrument.institution_id if instrument else actor.institution_id,
            actor_id=actor.id,
            instrument_id=instrument.id if instrument else None,
            row_version=instrument.row_version if instrument else 0,
            action=action,
            request_id=request.state.request_id,
            detail=detail or {},
        )
    )
