"""Release requests, clearances and an append-only decision history."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None

FROZEN = "id, instrument_id, institution_id, requested_by, reason, policy_snapshot, created_at"
ALLOWED = """(OLD.status = 'open' AND NEW.status IN ('on_hold', 'returned', 'approved', 'rejected', 'withdrawn'))
          OR (OLD.status = 'on_hold' AND NEW.status IN ('open', 'returned', 'withdrawn'))
          OR (OLD.status = 'returned' AND NEW.status IN ('open', 'withdrawn'))
          OR (OLD.status = 'approved' AND NEW.status = 'open')"""


def upgrade():
    op.create_table(
        "release_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("policy_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decided_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=False),
        sa.Column("decision_basis", sa.String(64), nullable=True),
        sa.Column("decision_key", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id", "institution_id"], ["instruments.id", "instruments.institution_id"]
        ),
        sa.CheckConstraint(
            "status IN ('open', 'on_hold', 'returned', 'approved', 'rejected', 'withdrawn')"
        ),
        sa.CheckConstraint(
            "status NOT IN ('approved', 'rejected')"
            " OR (decided_by IS NOT NULL AND decision_basis IS NOT NULL)",
            name="decision_recorded",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_requests_instrument_id", "release_requests", ["instrument_id"])
    op.create_index(
        "uq_release_live",
        "release_requests",
        ["instrument_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'on_hold', 'returned', 'approved')"),
    )
    op.create_table(
        "release_clearances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("release_requests.id"), nullable=False),
        sa.Column("clearance", sa.String(40), nullable=False),
        sa.Column("cleared_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("request_id", "clearance"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_clearances_request_id", "release_clearances", ["request_id"])
    op.create_table(
        "release_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), sa.ForeignKey("release_requests.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=False),
        sa.Column("basis", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_release_events_request_id", "release_events", ["request_id"])
    for table in ("release_clearances", "release_events"):
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
        )
    new = ", ".join("NEW." + c for c in FROZEN.split(", "))
    old = ", ".join("OLD." + c for c in FROZEN.split(", "))
    op.execute(f"""CREATE FUNCTION guard_release() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR ROW({new}) IS DISTINCT FROM ROW({old})
         OR NOT ({ALLOWED})
      THEN RAISE EXCEPTION 'Release request change not allowed'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON release_requests FOR EACH ROW EXECUTE FUNCTION guard_release()"
    )


def downgrade():
    op.drop_table("release_events")
    op.drop_table("release_clearances")
    op.drop_table("release_requests")
    op.execute("DROP FUNCTION guard_release()")
