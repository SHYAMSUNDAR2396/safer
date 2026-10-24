"""Asynchronous, expiring, owner-scoped exports."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("institution_ids", postgresql.ARRAY(sa.Uuid()), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("object_key", sa.String(200), nullable=True),
        sa.Column("object_version", sa.String(200), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("error", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'ready', 'failed')"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exports_user_id", "exports", ["user_id"])


def downgrade():
    op.drop_table("exports")
