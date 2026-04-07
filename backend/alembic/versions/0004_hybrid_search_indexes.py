"""hybrid search indexes

Revision ID: 0004_hybrid_search_indexes
Revises: 0003_pg_trgm_search
Create Date: 2026-03-29
"""

from alembic import op


revision = "0004_hybrid_search_indexes"
down_revision = "0003_pg_trgm_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ste_items_attributes_trgm "
        "ON ste_items USING gin ((CAST(attributes_json AS text)) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ste_items_search_vector "
        "ON ste_items USING gin ("
        "to_tsvector("
        "'simple', "
        "coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || coalesce(CAST(attributes_json AS text), '')"
        ")"
        ")"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ste_items_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_ste_items_attributes_trgm")
