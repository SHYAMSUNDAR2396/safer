"""Quarantined document metadata bound to exact object versions."""

import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

BOUND = "id, institution_id, instrument_id, filename, media_type, size_bytes, sha256, page_count, object_key, uploaded_by, created_at"


def upgrade():
    op.create_unique_constraint(
        "uq_instruments_id_institution", "instruments", ["id", "institution_id"]
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("media_type", sa.String(length=30), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("object_key", sa.String(length=200), nullable=False),
        sa.Column("object_version", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('pending', 'quarantined', 'failed')"),
        sa.CheckConstraint("status <> 'quarantined' OR object_version IS NOT NULL"),
        sa.CheckConstraint("media_type IN ('application/pdf', 'image/png', 'image/jpeg')"),
        sa.CheckConstraint("size_bytes > 0"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"]),
        sa.ForeignKeyConstraint(
            ["instrument_id", "institution_id"], ["instruments.id", "instruments.institution_id"]
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index("ix_documents_instrument_id", "documents", ["instrument_id"])
    # Only pending -> quarantined|failed may change, and only status/version; nothing is deleted.
    op.execute(f"""CREATE FUNCTION guard_document() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Documents cannot be deleted'; END IF;
      IF OLD.status <> 'pending' OR NEW.status = 'pending'
         OR ROW({", ".join("NEW." + c for c in BOUND.split(", "))})
            IS DISTINCT FROM ROW({", ".join("OLD." + c for c in BOUND.split(", "))})
      THEN RAISE EXCEPTION 'Document bindings are immutable'; END IF;
      RETURN NEW;
    END; $$""")
    op.execute(
        "CREATE TRIGGER immutable_binding BEFORE UPDATE OR DELETE ON documents FOR EACH ROW EXECUTE FUNCTION guard_document()"
    )


def downgrade():
    op.drop_table("documents")
    op.execute("DROP FUNCTION guard_document()")
    op.drop_constraint("uq_instruments_id_institution", "instruments")
