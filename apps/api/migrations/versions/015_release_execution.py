"""Release instruction, execution evidence and closure."""

import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

FROZEN = "id, instrument_id, institution_id, requested_by, reason, policy_snapshot, created_at"
TRANSITIONS = {
    "014": """(OLD.status = 'open' AND NEW.status IN ('on_hold', 'returned', 'approved', 'rejected', 'withdrawn'))
          OR (OLD.status = 'on_hold' AND NEW.status IN ('open', 'returned', 'withdrawn'))
          OR (OLD.status = 'returned' AND NEW.status IN ('open', 'withdrawn'))
          OR (OLD.status = 'approved' AND NEW.status = 'open')""",
}
TRANSITIONS["015"] = TRANSITIONS["014"].replace(
    "(OLD.status = 'approved' AND NEW.status = 'open')",
    "(OLD.status = 'approved' AND NEW.status IN ('open', 'closed'))",
)


def guard(allowed):
    new = ", ".join("NEW." + c for c in FROZEN.split(", "))
    old = ", ".join("OLD." + c for c in FROZEN.split(", "))
    return f"""CREATE OR REPLACE FUNCTION guard_release() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR ROW({new}) IS DISTINCT FROM ROW({old})
         OR NOT ({allowed})
      THEN RAISE EXCEPTION 'Release request change not allowed'; END IF;
      RETURN NEW;
    END; $$"""


def statuses(instrument, release, recorded):
    op.drop_constraint("instruments_status_check", "instruments")
    op.create_check_constraint(
        "instruments_status_check", "instruments", f"status IN ({instrument})"
    )
    op.drop_constraint("release_requests_status_check", "release_requests")
    op.create_check_constraint(
        "release_requests_status_check", "release_requests", f"status IN ({release})"
    )
    op.drop_constraint("decision_recorded", "release_requests")
    op.create_check_constraint(
        "decision_recorded",
        "release_requests",
        f"status NOT IN ({recorded}) OR (decided_by IS NOT NULL AND decision_basis IS NOT NULL)",
    )


def upgrade():
    statuses(
        "'draft', 'submitted', 'closed'",
        "'open', 'on_hold', 'returned', 'approved', 'rejected', 'withdrawn', 'closed'",
        "'approved', 'rejected', 'closed'",
    )
    op.execute(guard(TRANSITIONS["015"]))
    op.create_table(
        "release_instructions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("release_requests.id"), nullable=False),
        sa.Column("reference", sa.String(40), nullable=False),
        sa.Column("addressed_to", sa.String(120), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("issued_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("basis", sa.String(64), nullable=False),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.UniqueConstraint("request_id"),
        sa.UniqueConstraint("reference"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "release_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("release_requests.id"), nullable=False),
        sa.Column("executed_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("executed_on", sa.Date(), nullable=False),
        sa.Column("bank_transaction_ref", sa.String(100), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("observer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("executed_amount > 0"),
        sa.CheckConstraint(
            "method IN ('bank_portal', 'bank_email', 'bank_letter', 'phone_callback')"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_executions_request_id", "release_executions", ["request_id"])
    for table in ("release_instructions", "release_executions"):
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
        )


def downgrade():
    op.drop_table("release_executions")
    op.drop_table("release_instructions")
    op.execute(guard(TRANSITIONS["014"]))
    statuses(
        "'draft', 'submitted'",
        "'open', 'on_hold', 'returned', 'approved', 'rejected', 'withdrawn'",
        "'approved', 'rejected'",
    )
