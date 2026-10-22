"""Transactional outbox jobs and append-only attempt history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("dedup_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(300), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'dead')"),
        sa.CheckConstraint("attempts >= 0 AND attempts <= max_attempts"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedup_key"),
    )
    op.create_index(
        "ix_jobs_due",
        "jobs",
        ["available_at"],
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("error", sa.String(300), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "finished_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("outcome IN ('succeeded', 'retry', 'dead', 'stalled')"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON job_attempts FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
    )
    # Documents uploaded before the outbox still need scanning; dedup keys keep this idempotent.
    op.execute("""
        INSERT INTO jobs (id, kind, payload, dedup_key, status, attempts, max_attempts, last_error)
        SELECT gen_random_uuid(), 'scan_document', jsonb_build_object('document_id', d.id::text),
               'scan_document:' || d.id, 'queued', 0, 3, ''
        FROM documents d
        WHERE d.status = 'quarantined' AND NOT EXISTS (
            SELECT 1 FROM document_scans s WHERE s.document_id = d.id
              AND s.object_version = d.object_version AND s.outcome IN ('clean', 'infected', 'mismatch'))
        ON CONFLICT (dedup_key) DO NOTHING
    """)


def downgrade():
    op.drop_table("job_attempts")
    op.drop_table("jobs")
