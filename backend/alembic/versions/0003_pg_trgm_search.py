"""pg_trgm search support

Revision ID: 0003_pg_trgm_search
Revises: 0002_spell_corrections
Create Date: 2026-03-24
"""

from alembic import op


revision = "0003_pg_trgm_search"
down_revision = "0002_spell_corrections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ste_items_title_trgm "
        "ON ste_items USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ste_items_description_trgm "
        "ON ste_items USING gin (description gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ste_items_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_ste_items_title_trgm")
