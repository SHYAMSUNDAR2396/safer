"""Extraction runs and positioned field proposals (append-only)."""

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("extractor", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("text_layer", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("document_id", "extractor"),
        sa.CheckConstraint("status IN ('completed', 'manual_required', 'failed')"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extraction_runs_document_id", "extraction_runs", ["document_id"])
    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("extraction_runs.id"), nullable=False),
        sa.Column("field", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("value", sa.String(120), nullable=True),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column("snippet", sa.String(300), nullable=False),
        sa.UniqueConstraint("run_id", "field"),
        sa.CheckConstraint("status IN ('proposed', 'abstained')"),
        sa.CheckConstraint("status = 'abstained' OR value IS NOT NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extracted_fields_run_id", "extracted_fields", ["run_id"])
    for table in ("extraction_runs", "extracted_fields"):
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
        )


def downgrade():
    op.drop_table("extracted_fields")
    op.drop_table("extraction_runs")
