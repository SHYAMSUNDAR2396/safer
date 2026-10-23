"""Versioned, applicability-scoped policies with second-person publication."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

FROZEN = "id, code, version, applies_to, effective_from, effective_until, rules, note, owner_validated, drafted_by, created_at"


def upgrade():
    op.add_column(
        "obligations",
        sa.Column(
            "kind", sa.String(50), server_default="approval_security_deposit", nullable=False
        ),
    )
    op.create_table(
        "policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("applies_to", sa.String(50), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date(), nullable=True),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("owner_validated", sa.Boolean(), nullable=False),
        sa.Column("drafted_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("published_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("code", "version"),
        sa.CheckConstraint("code IN ('release')"),
        sa.CheckConstraint("status IN ('draft', 'published')"),
        sa.CheckConstraint("effective_until IS NULL OR effective_until > effective_from"),
        sa.CheckConstraint("published_by IS DISTINCT FROM drafted_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    new = ", ".join("NEW." + c for c in FROZEN.split(", "))
    old = ", ".join("OLD." + c for c in FROZEN.split(", "))
    op.execute(f"""CREATE FUNCTION guard_policy() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR OLD.status <> 'draft' OR NEW.status <> 'published'
         OR ROW({new}) IS DISTINCT FROM ROW({old})
      THEN RAISE EXCEPTION 'Policies change only by publishing a draft'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON policies FOR EACH ROW EXECUTE FUNCTION guard_policy()"
    )


def downgrade():
    op.drop_table("policies")
    op.execute("DROP FUNCTION guard_policy()")
    op.drop_column("obligations", "kind")
