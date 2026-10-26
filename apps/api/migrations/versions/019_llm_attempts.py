"""Durable model-call reservations and redacted usage metadata."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "llm_attempts",
        sa.Column("id", postgresql.UUID(), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "instrument_id", postgresql.UUID(), sa.ForeignKey("instruments.id"), nullable=False
        ),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("basis_sha256", sa.String(64), nullable=False),
        sa.Column("model", sa.String(60), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("reserved_microusd", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("reserved_microusd >= 0 AND total_tokens >= 0"),
        sa.CheckConstraint("status IN ('reserved','completed','failed','discarded')"),
    )
    op.create_index("ix_llm_attempts_actor_id", "llm_attempts", ["actor_id"])
    op.create_index("ix_llm_attempts_created_at", "llm_attempts", ["created_at"])


def downgrade():
    op.drop_table("llm_attempts")
