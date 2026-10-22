"""Bank confirmation requests/responses (simulator provider only)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

METHODS = "'bank_portal', 'bank_email', 'bank_letter', 'phone_callback'"


def upgrade():
    op.drop_constraint("evidence_records_method_check", "evidence_records")
    op.create_check_constraint(
        "evidence_records_method_check",
        "evidence_records",
        f"method IN ({METHODS}, 'bank_simulator')",
    )
    op.create_table(
        "bank_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("submission_id", sa.Uuid(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id", "institution_id"], ["instruments.id", "instruments.institution_id"]
        ),
        sa.CheckConstraint("provider IN ('simulator')"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_requests_instrument_id", "bank_requests", ["instrument_id"])
    op.create_table(
        "bank_responses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("bank_requests.id"), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("detail", sa.String(200), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("outcome IN ('confirmed', 'not_found', 'timeout', 'rejected', 'stale')"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    for table in ("bank_requests", "bank_responses"):
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
        )


def downgrade():
    op.drop_table("bank_responses")
    op.drop_table("bank_requests")
    op.drop_constraint("evidence_records_method_check", "evidence_records")
    op.create_check_constraint(
        "evidence_records_method_check", "evidence_records", f"method IN ({METHODS})"
    )
