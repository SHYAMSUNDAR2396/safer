"""Scoped grants with expiry, revocation, delegation and dual control; replaces assignments."""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

FROZEN = "id, user_id, authority, institution_id, valid_from, valid_until, requested_by, delegated_from, reason, created_at"


def upgrade():
    op.drop_constraint("users_role_check", "users")
    op.create_check_constraint(
        "users_role_check", "users", "role IN ('institution_user', 'auditor', 'reviewer', 'admin')"
    )
    op.create_table(
        "grants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("authority", sa.String(30), nullable=False),
        sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "valid_from",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("delegated_from", sa.Uuid(), sa.ForeignKey("grants.id"), nullable=True),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("revoke_reason", sa.String(300), nullable=False, server_default=""),
        sa.CheckConstraint("authority IN ('review', 'release_approve')"),
        sa.CheckConstraint("status IN ('pending', 'active', 'rejected', 'revoked', 'expired')"),
        sa.CheckConstraint("requested_by IS DISTINCT FROM user_id"),
        sa.CheckConstraint("approved_by IS DISTINCT FROM user_id"),
        sa.CheckConstraint(
            "authority <> 'release_approve' OR status IN ('pending', 'rejected')"
            " OR (approved_by IS NOT NULL AND approved_by IS DISTINCT FROM requested_by)",
            name="dual_control",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_grants_user_id", "grants", ["user_id"])
    op.create_index("ix_grants_institution_id", "grants", ["institution_id"])
    op.create_index(
        "uq_grants_live",
        "grants",
        ["user_id", "authority", "institution_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'active')"),
    )
    new = ", ".join("NEW." + c for c in FROZEN.split(", "))
    old = ", ".join("OLD." + c for c in FROZEN.split(", "))
    op.execute(f"""CREATE FUNCTION guard_grant() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' OR ROW({new}) IS DISTINCT FROM ROW({old}) THEN
        RAISE EXCEPTION 'Grant history is immutable';
      END IF;
      IF NOT ((OLD.status = 'pending' AND NEW.status IN ('active', 'rejected'))
           OR (OLD.status = 'active' AND NEW.status IN ('revoked', 'expired'))) THEN
        RAISE EXCEPTION 'Invalid grant transition % -> %', OLD.status, NEW.status;
      END IF;
      IF OLD.status <> 'pending' AND NEW.approved_by IS DISTINCT FROM OLD.approved_by THEN
        RAISE EXCEPTION 'Approval cannot be rewritten';
      END IF;
      RETURN NEW;
    END; $$""")
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON grants FOR EACH ROW EXECUTE FUNCTION guard_grant()"
    )
    op.execute("""
        INSERT INTO grants (id, user_id, authority, institution_id, status, reason, decided_at)
        SELECT gen_random_uuid(), reviewer_id, 'review', institution_id, 'active',
               'Migrated from review assignment', now()
        FROM review_assignments
    """)
    op.drop_table("review_assignments")


def downgrade():
    op.create_table(
        "review_assignments",
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id"), primary_key=True),
    )
    op.execute("""
        INSERT INTO review_assignments
        SELECT DISTINCT user_id, institution_id FROM grants
        WHERE authority = 'review' AND status = 'active'
    """)
    op.drop_table("grants")
    op.execute("DROP FUNCTION guard_grant()")
    op.drop_constraint("users_role_check", "users")
    op.create_check_constraint(
        "users_role_check", "users", "role IN ('institution_user', 'auditor', 'reviewer')"
    )
