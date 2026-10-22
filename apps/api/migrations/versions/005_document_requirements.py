"""Configured document requirements per obligation; document kinds."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

GUARD = """CREATE OR REPLACE FUNCTION guard_document() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Documents cannot be deleted'; END IF;
      IF OLD.status <> 'pending' OR NEW.status = 'pending'
         OR ROW({new}) IS DISTINCT FROM ROW({old})
      THEN RAISE EXCEPTION 'Document bindings are immutable'; END IF;
      RETURN NEW;
    END; $$"""
BOUND = "id, institution_id, instrument_id, filename, media_type, size_bytes, sha256, page_count, object_key, uploaded_by, created_at"


def guard(columns):
    cols = columns.split(", ")
    return GUARD.format(
        new=", ".join("NEW." + c for c in cols), old=", ".join("OLD." + c for c in cols)
    )


def upgrade():
    op.add_column(
        "obligations",
        sa.Column(
            "required_documents",
            postgresql.ARRAY(sa.String(length=30)),
            server_default="{fdr_certificate}",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_obligations_required_documents",
        "obligations",
        "required_documents <@ ARRAY['fdr_certificate', 'bank_letter']::varchar[]",
    )
    # Earlier uploads had no declared kind; they stay as history and satisfy no requirement.
    op.add_column(
        "documents",
        sa.Column("kind", sa.String(length=30), server_default="other", nullable=False),
    )
    op.alter_column("documents", "kind", server_default=None)
    op.create_check_constraint(
        "ck_documents_kind", "documents", "kind IN ('fdr_certificate', 'bank_letter', 'other')"
    )
    op.execute(guard(BOUND + ", kind"))


def downgrade():
    op.execute(guard(BOUND))
    op.drop_column("documents", "kind")
    op.drop_column("obligations", "required_documents")
