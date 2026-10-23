"""Provision synthetic identities and illustrative obligations; never overwrites existing data."""

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from safer.config import Settings
from safer.models import Grant, Institution, Obligation, Policy, User
from safer.storage import client, ensure_bucket

NAMES = ("alpha", "beta", "auditor", "reviewer", "admin1", "admin2", "reviewer2")


def populate(db: Session, issuer: str):
    for offset, name in [(100, "Alpha Technical Institute"), (200, "Beta Technical Institute")]:
        id = UUID(int=offset)
        if not db.get(Institution, id):
            db.add(Institution(id=id, name=name))
            db.flush()
        oid = UUID(int=offset + 1)
        if not db.get(Obligation, oid):
            db.add(
                Obligation(
                    id=oid,
                    institution_id=id,
                    title="Demo approval obligation · illustrative policy",
                    required_amount="500000.00",
                )
            )
    if not db.get(Institution, UUID(int=300)):
        db.add(Institution(id=UUID(int=300), name="AICTE Regulation Bureau · demo"))
        db.flush()
    for suffix, name, institution, role in [
        (1, "Alpha institution officer", 100, "institution_user"),
        (2, "Beta institution officer", 200, "institution_user"),
        (3, "Alpha read-only auditor", 100, "auditor"),
        (4, "Regulation Bureau reviewer", 300, "reviewer"),
        (5, "Access administrator one", 300, "admin"),
        (6, "Access administrator two", 300, "admin"),
        (7, "Second Bureau reviewer", 300, "reviewer"),
    ]:
        subject = f"00000000-0000-4000-8000-{suffix:012d}"
        id = UUID(subject)
        existing = db.get(User, id)
        if existing and not existing.email:  # additive: earlier seeds had no addresses
            existing.email = f"{NAMES[suffix - 1]}@example.invalid"
        if not existing:
            db.add(
                User(
                    id=id,
                    issuer=issuer,
                    subject=subject,
                    display_name=name,
                    email=f"{NAMES[suffix - 1]}@example.invalid",
                    institution_id=UUID(int=institution),
                    role=role,
                )
            )
    db.flush()
    # The demo reviewer covers Alpha only, so Beta's cases demonstrate the scope boundary.
    reviewer, alpha = UUID("00000000-0000-4000-8000-000000000004"), UUID(int=100)
    if not db.scalar(select(Grant.id).where(Grant.user_id == reviewer)):
        db.add(
            Grant(
                user_id=reviewer,
                authority="review",
                institution_id=alpha,
                status="active",
                requested_by=UUID("00000000-0000-4000-8000-000000000005"),
                approved_by=UUID("00000000-0000-4000-8000-000000000005"),
                reason="Demo portfolio: Alpha Technical Institute",
            )
        )
    if not db.scalar(select(Policy.id).where(Policy.code == "release")):
        db.add(
            Policy(
                code="release",
                version=1,
                applies_to="*",
                effective_from=date(2026, 1, 1),
                rules={
                    "clearances": ["no_dues_certificate", "closure_approval_letter"],
                    "release_not_before": "obligation_end",
                },
                note="Illustrative release rules for the demonstration; not AICTE policy",
                status="published",
                drafted_by=UUID("00000000-0000-4000-8000-000000000005"),
                published_by=UUID("00000000-0000-4000-8000-000000000006"),
                published_at=datetime.now(UTC),
            )
        )
    db.commit()


if __name__ == "__main__":
    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value(), hide_parameters=True)
    with Session(engine) as db:
        populate(db, settings.oidc_issuer)
    engine.dispose()
    ensure_bucket(client(settings), settings.s3_bucket)
    print(
        "Synthetic institutions, memberships, obligations and versioned document bucket are ready. "
        "Existing records preserved."
    )
