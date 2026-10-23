"""Replacement links between FDRs of the same institution and obligation."""

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

FROZEN = "id, institution_id, obligation_id, predecessor_id, successor_id, proposed_by, proposed_at"


def upgrade():
    op.create_unique_constraint(
        "uq_instruments_id_institution_obligation",
        "instruments",
        ["id", "institution_id", "obligation_id"],
    )
    target = ["instruments.id", "instruments.institution_id", "instruments.obligation_id"]
    op.create_table(
        "replacement_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("obligation_id", sa.Uuid(), nullable=False),
        sa.Column("predecessor_id", sa.Uuid(), nullable=False),
        sa.Column("successor_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("proposed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "proposed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=False),
        sa.ForeignKeyConstraint(["predecessor_id", "institution_id", "obligation_id"], target),
        sa.ForeignKeyConstraint(["successor_id", "institution_id", "obligation_id"], target),
        sa.CheckConstraint("predecessor_id <> successor_id"),
        sa.CheckConstraint("status IN ('proposed', 'accepted', 'rejected')"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("predecessor_id", "successor_id"):
        op.create_index(f"ix_replacement_links_{column}", "replacement_links", [column])
        # One live link per FDR on each side: replacements are 1:1 until split support exists.
        op.create_index(
            f"uq_replacement_live_{column}",
            "replacement_links",
            [column],
            unique=True,
            postgresql_where=sa.text("status IN ('proposed', 'accepted')"),
        )
    new = ", ".join("NEW." + c for c in FROZEN.split(", "))
    old = ", ".join("OLD." + c for c in FROZEN.split(", "))
    op.execute(f"""CREATE FUNCTION guard_replacement() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR OLD.status <> 'proposed' OR NEW.status = 'proposed'
         OR ROW({new}) IS DISTINCT FROM ROW({old})
      THEN RAISE EXCEPTION 'Replacement history is immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON replacement_links FOR EACH ROW EXECUTE FUNCTION guard_replacement()"
    )


def downgrade():
    op.drop_table("replacement_links")
    op.execute("DROP FUNCTION guard_replacement()")
    op.drop_constraint("uq_instruments_id_institution_obligation", "instruments")
