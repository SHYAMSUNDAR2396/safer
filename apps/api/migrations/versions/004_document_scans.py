"""Append-only malware scan results; system-actor audit events."""

import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("object_version", sa.String(length=200), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("engine", sa.String(length=100), nullable=False),
        sa.Column("signature", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("outcome IN ('clean', 'infected', 'mismatch', 'error')"),
        sa.CheckConstraint("outcome <> 'clean' OR sha256 IS NOT NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_scans_document_id", "document_scans", ["document_id"])
    op.execute(
        "CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON document_scans FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
    )
    op.alter_column("audit_events", "actor_id", nullable=True)


def downgrade():
    # actor_id stays nullable: restoring NOT NULL would require deleting system audit history.
    op.drop_table("document_scans")
