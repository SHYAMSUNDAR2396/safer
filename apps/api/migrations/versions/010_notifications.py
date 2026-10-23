"""User email addresses and per-recipient notifications with delivery state."""

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

FROZEN = "id, instrument_id, institution_id, reminder_id, recipient_id, channel, subject, body, created_at"


def upgrade():
    op.add_column("users", sa.Column("email", sa.String(254), nullable=True))
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("reminder_id", sa.Uuid(), sa.ForeignKey("reminders.id"), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("subject", sa.String(150), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_status", sa.String(20), nullable=False),
        sa.Column("delivery_detail", sa.String(200), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["instrument_id", "institution_id"], ["instruments.id", "instruments.institution_id"]
        ),
        sa.UniqueConstraint("reminder_id", "recipient_id", "channel"),
        sa.CheckConstraint("channel IN ('in_app', 'email')"),
        sa.CheckConstraint(
            "delivery_status IN ('not_applicable', 'pending', 'sent', 'failed', 'uncertain')"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
    new = ", ".join("NEW." + c for c in FROZEN.split(", "))
    old = ", ".join("OLD." + c for c in FROZEN.split(", "))
    # Content and recipient are frozen; only read and delivery state may change.
    op.execute(f"""CREATE FUNCTION guard_notification() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR ROW({new}) IS DISTINCT FROM ROW({old})
      THEN RAISE EXCEPTION 'Notification content is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute(
        "CREATE TRIGGER immutable_content BEFORE UPDATE OR DELETE ON notifications FOR EACH ROW EXECUTE FUNCTION guard_notification()"
    )


def downgrade():
    op.drop_table("notifications")
    op.execute("DROP FUNCTION guard_notification()")
    op.drop_column("users", "email")
