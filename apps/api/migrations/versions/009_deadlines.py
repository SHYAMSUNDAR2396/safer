"""Obligation coverage dates, versioned reminder schedules and generated reminders."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("obligations", sa.Column("required_until", sa.Date(), nullable=True))
    op.create_table(
        "reminder_schedules",
        sa.Column("version", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("offsets_days", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("action_lead_days", sa.Integer(), nullable=False),
        sa.Column("escalate_after_days", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(200), nullable=False),
        sa.CheckConstraint("cardinality(offsets_days) > 0 AND 0 < ALL(offsets_days)"),
        sa.CheckConstraint("action_lead_days > 0 AND escalate_after_days > 0"),
        sa.PrimaryKeyConstraint("version"),
    )
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("step", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("owner_role", sa.String(20), nullable=False),
        sa.Column(
            "schedule_version",
            sa.Integer(),
            sa.ForeignKey("reminder_schedules.version"),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("late", sa.Boolean(), nullable=False),
        sa.Column("message", sa.String(300), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id", "institution_id"], ["instruments.id", "instruments.institution_id"]
        ),
        sa.UniqueConstraint("instrument_id", "step"),
        sa.CheckConstraint("kind IN ('maturity_reminder', 'action_due', 'escalation')"),
        sa.CheckConstraint("owner_role IN ('institution', 'reviewer')"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reminders_instrument_id", "reminders", ["instrument_id"])
    op.create_index("ix_instruments_maturity_date", "instruments", ["maturity_date"])
    for table in ("reminder_schedules", "reminders"):
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
        )
    # Illustrative default policy; the policy owner must validate real values (SAF-018).
    op.execute(
        "INSERT INTO reminder_schedules VALUES "
        "(1, '{90,60,30,7}', 30, 7, '2026-01-01T00:00:00+05:30', 'Illustrative demo schedule')"
    )


def downgrade():
    op.drop_index("ix_instruments_maturity_date", "instruments")
    op.drop_table("reminders")
    op.drop_table("reminder_schedules")
    op.drop_column("obligations", "required_until")
