"""user collections

Revision ID: 0005_user_collections
Revises: 0004_hybrid_search_indexes
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_user_collections"
down_revision = "0004_hybrid_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "favorites",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("ste_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ste_id"], ["ste_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ste_id", name="uq_favorites_user_ste"),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])
    op.create_index("ix_favorites_ste_id", "favorites", ["ste_id"])

    op.create_table(
        "comparison_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("ste_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ste_id"], ["ste_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ste_id", name="uq_comparison_items_user_ste"),
    )
    op.create_index("ix_comparison_items_user_id", "comparison_items", ["user_id"])
    op.create_index("ix_comparison_items_ste_id", "comparison_items", ["ste_id"])

    op.create_table(
        "cart_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("ste_id", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ste_id"], ["ste_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ste_id", name="uq_cart_items_user_ste"),
    )
    op.create_index("ix_cart_items_user_id", "cart_items", ["user_id"])
    op.create_index("ix_cart_items_ste_id", "cart_items", ["ste_id"])


def downgrade() -> None:
    op.drop_index("ix_cart_items_ste_id", table_name="cart_items")
    op.drop_index("ix_cart_items_user_id", table_name="cart_items")
    op.drop_table("cart_items")

    op.drop_index("ix_comparison_items_ste_id", table_name="comparison_items")
    op.drop_index("ix_comparison_items_user_id", table_name="comparison_items")
    op.drop_table("comparison_items")

    op.drop_index("ix_favorites_ste_id", table_name="favorites")
    op.drop_index("ix_favorites_user_id", table_name="favorites")
    op.drop_table("favorites")
