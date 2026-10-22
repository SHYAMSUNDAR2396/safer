"""Reviewer role, assignment portfolio, independent evidence and discrepancy threads."""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

FIELDS = "'bank_name', 'bank_reference', 'principal_amount', 'issue_date', 'maturity_date'"
HISTORY = ("evidence_records", "discrepancies", "discrepancy_replies")


def case_columns():
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
    ]


def created():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def case_fk():
    return sa.ForeignKeyConstraint(
        ["instrument_id", "institution_id"], ["instruments.id", "instruments.institution_id"]
    )


def upgrade():
    op.drop_constraint("users_role_check", "users")
    op.create_check_constraint(
        "users_role_check", "users", "role IN ('institution_user', 'auditor', 'reviewer')"
    )
    op.create_table(
        "review_assignments",
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id"), primary_key=True),
    )
    op.create_table(
        "evidence_records",
        *case_columns(),
        sa.Column("field", sa.String(30), nullable=False),
        sa.Column("value", sa.String(120), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("observer_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        created(),
        case_fk(),
        sa.CheckConstraint(f"field IN ({FIELDS})"),
        sa.CheckConstraint(
            "method IN ('bank_portal', 'bank_email', 'bank_letter', 'phone_callback')"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "discrepancies",
        *case_columns(),
        sa.Column("field", sa.String(30), nullable=True),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("raised_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        created(),
        case_fk(),
        sa.CheckConstraint(f"field IS NULL OR field IN ({FIELDS})"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "discrepancy_replies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discrepancy_id", sa.Uuid(), sa.ForeignKey("discrepancies.id"), nullable=False),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        created(),
        sa.CheckConstraint("kind IN ('response', 'resolution')"),
        sa.PrimaryKeyConstraint("id"),
    )
    for table, column in [
        ("evidence_records", "instrument_id"),
        ("discrepancies", "instrument_id"),
        ("discrepancy_replies", "discrepancy_id"),
    ]:
        op.create_index(f"ix_{table}_{column}", table, [column])
    # A discrepancy can be resolved once, even under concurrent requests.
    op.create_index(
        "uq_discrepancy_resolution",
        "discrepancy_replies",
        ["discrepancy_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'resolution'"),
    )
    for table in HISTORY:
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
        )


def downgrade():
    for table in reversed(HISTORY):
        op.drop_table(table)
    op.drop_table("review_assignments")
    op.drop_constraint("users_role_check", "users")
    op.create_check_constraint(
        "users_role_check", "users", "role IN ('institution_user', 'auditor')"
    )
