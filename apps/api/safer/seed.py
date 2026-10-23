"""Provision synthetic identities and illustrative obligations; never overwrites existing data."""

from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from safer.config import Settings
from safer.models import Institution, Obligation, ReviewAssignment, User
from safer.storage import client, ensure_bucket


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
    ]:
        subject = f"00000000-0000-4000-8000-{suffix:012d}"
        id = UUID(subject)
        existing = db.get(User, id)
        if existing and not existing.email:  # additive: earlier seeds had no addresses
            existing.email = (
                f"{('alpha', 'beta', 'auditor', 'reviewer')[suffix - 1]}@example.invalid"
            )
        if not existing:
            db.add(
                User(
                    id=id,
                    issuer=issuer,
                    subject=subject,
                    display_name=name,
                    email=f"{('alpha', 'beta', 'auditor', 'reviewer')[suffix - 1]}@example.invalid",
                    institution_id=UUID(int=institution),
                    role=role,
                )
            )
    db.flush()
    # The demo reviewer covers Alpha only, so Beta's cases demonstrate the scope boundary.
    reviewer, alpha = UUID("00000000-0000-4000-8000-000000000004"), UUID(int=100)
    if not db.get(ReviewAssignment, (reviewer, alpha)):
        db.add(ReviewAssignment(reviewer_id=reviewer, institution_id=alpha))
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
