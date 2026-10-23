from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("issuer", "subject"),
        CheckConstraint("role IN ('institution_user', 'auditor', 'reviewer', 'admin')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer: Mapped[str] = mapped_column(String(300))
    subject: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(254))
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"))
    role: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SessionRow(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    csrf_token: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Obligation(Base):
    __tablename__ = "obligations"
    __table_args__ = (
        UniqueConstraint("id", "institution_id"),
        CheckConstraint("required_amount > 0"),
        CheckConstraint("required_documents <@ ARRAY['fdr_certificate', 'bank_letter']::varchar[]"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    required_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    # Document kinds that must be current and scanned clean before submission.
    required_documents: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)), server_default="{fdr_certificate}"
    )
    # The obligation's own coverage end; None means cover is required until released.
    required_until: Mapped[date | None]


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["obligation_id", "institution_id"], ["obligations.id", "obligations.institution_id"]
        ),
        CheckConstraint("principal_amount > 0"),
        CheckConstraint("maturity_date > issue_date"),
        CheckConstraint("status IN ('draft', 'submitted')"),
        CheckConstraint("currency = 'INR'"),
        UniqueConstraint("id", "institution_id"),
        UniqueConstraint("id", "institution_id", "obligation_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    obligation_id: Mapped[UUID]
    bank_name: Mapped[str] = mapped_column(String(120))
    bank_reference: Mapped[str] = mapped_column(String(100))
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    issue_date: Mapped[date]
    maturity_date: Mapped[date]
    status: Mapped[str] = mapped_column(String(20), default="draft")
    row_version: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id"), unique=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    """Uploaded bytes live in object storage; this row binds them to one exact version + hash."""

    __tablename__ = "documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["instrument_id", "institution_id"], ["instruments.id", "instruments.institution_id"]
        ),
        CheckConstraint("status IN ('pending', 'quarantined', 'failed')"),
        CheckConstraint("status <> 'quarantined' OR object_version IS NOT NULL"),
        CheckConstraint("media_type IN ('application/pdf', 'image/png', 'image/jpeg')"),
        CheckConstraint("size_bytes > 0"),
        CheckConstraint("kind IN ('fdr_certificate', 'bank_letter', 'other')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"))
    instrument_id: Mapped[UUID] = mapped_column(index=True)
    filename: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    media_type: Mapped[str] = mapped_column(String(30))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int | None]
    object_key: Mapped[str] = mapped_column(String(200), unique=True)
    object_version: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentScan(Base):
    """Append-only scan result, bound to the exact object version and the bytes' SHA-256."""

    __tablename__ = "document_scans"
    __table_args__ = (
        CheckConstraint("outcome IN ('clean', 'infected', 'mismatch', 'error')"),
        CheckConstraint("outcome <> 'clean' OR sha256 IS NOT NULL"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    object_version: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(20))
    engine: Mapped[str] = mapped_column(String(100), default="")
    signature: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Grant(Base):
    """Scoped, time-limited authority. Sensitive grants need a second admin (enforced in DB)."""

    __tablename__ = "grants"
    __table_args__ = (
        CheckConstraint("authority IN ('review', 'release_approve')"),
        CheckConstraint("status IN ('pending', 'active', 'rejected', 'revoked', 'expired')"),
        CheckConstraint("requested_by IS DISTINCT FROM user_id"),
        CheckConstraint("approved_by IS DISTINCT FROM user_id"),
        CheckConstraint(
            "authority <> 'release_approve' OR status IN ('pending', 'rejected')"
            " OR (approved_by IS NOT NULL AND approved_by IS DISTINCT FROM requested_by)",
            name="dual_control",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    authority: Mapped[str] = mapped_column(String(30))
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    delegated_from: Mapped[UUID | None] = mapped_column(ForeignKey("grants.id"))
    reason: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    revoke_reason: Mapped[str] = mapped_column(String(300), default="")


FIELDS = "'bank_name', 'bank_reference', 'principal_amount', 'issue_date', 'maturity_date'"


def case_fk():
    return ForeignKeyConstraint(
        ["instrument_id", "institution_id"], ["instruments.id", "instruments.institution_id"]
    )


class EvidenceRecord(Base):
    """An independently obtained fact about one field, never derived from uploaded claims."""

    __tablename__ = "evidence_records"
    __table_args__ = (
        case_fk(),
        CheckConstraint(f"field IN ({FIELDS})"),
        CheckConstraint(
            "method IN ('bank_portal', 'bank_email', 'bank_letter', 'phone_callback',"
            " 'bank_simulator')"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(index=True)
    institution_id: Mapped[UUID]
    field: Mapped[str] = mapped_column(String(30))
    value: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(200))
    method: Mapped[str] = mapped_column(String(30))
    observer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Discrepancy(Base):
    __tablename__ = "discrepancies"
    __table_args__ = (case_fk(), CheckConstraint(f"field IS NULL OR field IN ({FIELDS})"))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(index=True)
    institution_id: Mapped[UUID]
    field: Mapped[str | None] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(1000))
    raised_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DiscrepancyReply(Base):
    __tablename__ = "discrepancy_replies"
    __table_args__ = (CheckConstraint("kind IN ('response', 'resolution')"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    discrepancy_id: Mapped[UUID] = mapped_column(ForeignKey("discrepancies.id"), index=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BankRequest(Base):
    """A confirmation request bound to one case version; provider 'simulator' is synthetic."""

    __tablename__ = "bank_requests"
    __table_args__ = (case_fk(), CheckConstraint("provider IN ('simulator')"))
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(index=True)
    institution_id: Mapped[UUID]
    submission_id: Mapped[UUID] = mapped_column(ForeignKey("submissions.id"))
    row_version: Mapped[int]
    provider: Mapped[str] = mapped_column(String(30))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BankResponse(Base):
    __tablename__ = "bank_responses"
    __table_args__ = (
        CheckConstraint("outcome IN ('confirmed', 'not_found', 'timeout', 'rejected', 'stale')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("bank_requests.id"), unique=True)
    outcome: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(200), default="")
    payload: Mapped[dict | None] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Job(Base):
    """Outbox row written with the business change; the broker only carries its id."""

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'dead')"),
        CheckConstraint("attempts >= 0 AND attempts <= max_attempts"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB)
    dedup_key: Mapped[str] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobAttempt(Base):
    __tablename__ = "job_attempts"
    __table_args__ = (CheckConstraint("outcome IN ('succeeded', 'retry', 'dead', 'stalled')"),)
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), index=True)
    attempt: Mapped[int]
    outcome: Mapped[str] = mapped_column(String(20))
    error: Mapped[str] = mapped_column(String(300), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReminderSchedule(Base):
    """Immutable, versioned reminder policy; the latest version in effect applies going forward."""

    __tablename__ = "reminder_schedules"
    __table_args__ = (
        CheckConstraint("cardinality(offsets_days) > 0 AND 0 < ALL(offsets_days)"),
        CheckConstraint("action_lead_days > 0 AND escalate_after_days > 0"),
    )
    version: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    offsets_days: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    action_lead_days: Mapped[int]
    escalate_after_days: Mapped[int]
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(String(200), default="")


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        case_fk(),
        UniqueConstraint("instrument_id", "step"),
        CheckConstraint("kind IN ('maturity_reminder', 'action_due', 'escalation')"),
        CheckConstraint("owner_role IN ('institution', 'reviewer')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(index=True)
    institution_id: Mapped[UUID]
    step: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(30))
    owner_role: Mapped[str] = mapped_column(String(20))
    schedule_version: Mapped[int] = mapped_column(ForeignKey("reminder_schedules.version"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    late: Mapped[bool]
    message: Mapped[str] = mapped_column(String(300))


class Notification(Base):
    """One message to one person on one channel; content is frozen, delivery state is not."""

    __tablename__ = "notifications"
    __table_args__ = (
        case_fk(),
        UniqueConstraint("reminder_id", "recipient_id", "channel"),
        CheckConstraint("channel IN ('in_app', 'email')"),
        CheckConstraint(
            "delivery_status IN ('not_applicable', 'pending', 'sent', 'failed', 'uncertain')"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID]
    institution_id: Mapped[UUID]
    reminder_id: Mapped[UUID] = mapped_column(ForeignKey("reminders.id"))
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10))
    subject: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str] = mapped_column(String(20))
    delivery_detail: Mapped[str] = mapped_column(String(200), default="")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReplacementLink(Base):
    """One FDR replacing another for the same institution and obligation (1:1 only)."""

    __tablename__ = "replacement_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["predecessor_id", "institution_id", "obligation_id"],
            ["instruments.id", "instruments.institution_id", "instruments.obligation_id"],
        ),
        ForeignKeyConstraint(
            ["successor_id", "institution_id", "obligation_id"],
            ["instruments.id", "instruments.institution_id", "instruments.obligation_id"],
        ),
        CheckConstraint("predecessor_id <> successor_id"),
        CheckConstraint("status IN ('proposed', 'accepted', 'rejected')"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    institution_id: Mapped[UUID]
    obligation_id: Mapped[UUID]
    predecessor_id: Mapped[UUID] = mapped_column(index=True)
    successor_id: Mapped[UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    proposed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str] = mapped_column(String(500), default="")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"))
    instrument_id: Mapped[UUID | None] = mapped_column(ForeignKey("instruments.id"), index=True)
    # None marks a system actor (the malware scanner), never an anonymous user.
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50))
    row_version: Mapped[int] = mapped_column(default=0)
    request_id: Mapped[str] = mapped_column(String(36))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
