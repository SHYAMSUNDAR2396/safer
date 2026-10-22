"""Protect audit and submission snapshots from ordinary SQL mutation."""

from alembic import op

revision = "002"
down_revision = "0db8029ab7da"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION reject_history_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Historical records cannot be updated or deleted'; END; $$""")
    for table in ("audit_events", "submissions"):
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_history_mutation()"
        )


def downgrade():
    for table in ("audit_events", "submissions"):
        op.execute(f"DROP TRIGGER immutable_history ON {table}")
    op.execute("DROP FUNCTION reject_history_mutation()")
