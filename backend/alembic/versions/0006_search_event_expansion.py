"""expand search events and impressions

Revision ID: 0006_search_event_expansion
Revises: 0005_user_collections
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_search_event_expansion"
down_revision = "0005_user_collections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "search_events",
        sa.Column("role", sa.String(length=64), nullable=False, server_default="customer"),
    )
    op.add_column("search_events", sa.Column("supplier_id", sa.String(length=64), nullable=True))
    op.add_column("search_events", sa.Column("category_id", sa.String(length=64), nullable=True))
    op.add_column("search_events", sa.Column("query_text", sa.Text(), nullable=True))
    op.add_column("search_events", sa.Column("normalized_query", sa.Text(), nullable=True))
    op.add_column("search_events", sa.Column("corrected_query", sa.Text(), nullable=True))
    op.add_column("search_events", sa.Column("page_type", sa.String(length=64), nullable=True))
    op.add_column("search_events", sa.Column("page_url", sa.Text(), nullable=True))
    op.add_column("search_events", sa.Column("referrer", sa.String(length=255), nullable=True))
    op.add_column("search_events", sa.Column("rank_position", sa.Integer(), nullable=True))
    op.add_column("search_events", sa.Column("results_page", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "fk_search_events_supplier_id_suppliers",
        "search_events",
        "suppliers",
        ["supplier_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_search_events_category_id_categories",
        "search_events",
        "categories",
        ["category_id"],
        ["id"],
    )
    op.create_index("ix_search_events_supplier_id", "search_events", ["supplier_id"])
    op.create_index("ix_search_events_category_id", "search_events", ["category_id"])
    op.create_index("ix_search_events_role", "search_events", ["role"])

    op.create_table(
        "search_impressions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("search_session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("ste_id", sa.String(length=64), nullable=False),
        sa.Column("supplier_id", sa.String(length=64), nullable=True),
        sa.Column("category_id", sa.String(length=64), nullable=True),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("results_page", sa.Integer(), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("rendered_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["search_session_id"], ["search_sessions.id"]),
        sa.ForeignKeyConstraint(["ste_id"], ["ste_items.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_search_impressions_search_session_id",
        "search_impressions",
        ["search_session_id"],
    )
    op.create_index("ix_search_impressions_user_id", "search_impressions", ["user_id"])
    op.create_index(
        "ix_search_impressions_organization_id",
        "search_impressions",
        ["organization_id"],
    )
    op.create_index("ix_search_impressions_ste_id", "search_impressions", ["ste_id"])
    op.create_index(
        "ix_search_impressions_supplier_id",
        "search_impressions",
        ["supplier_id"],
    )
    op.create_index(
        "ix_search_impressions_category_id",
        "search_impressions",
        ["category_id"],
    )

    op.alter_column("search_events", "role", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_search_impressions_category_id", table_name="search_impressions")
    op.drop_index("ix_search_impressions_supplier_id", table_name="search_impressions")
    op.drop_index("ix_search_impressions_ste_id", table_name="search_impressions")
    op.drop_index("ix_search_impressions_organization_id", table_name="search_impressions")
    op.drop_index("ix_search_impressions_user_id", table_name="search_impressions")
    op.drop_index("ix_search_impressions_search_session_id", table_name="search_impressions")
    op.drop_table("search_impressions")

    op.drop_index("ix_search_events_role", table_name="search_events")
    op.drop_index("ix_search_events_category_id", table_name="search_events")
    op.drop_index("ix_search_events_supplier_id", table_name="search_events")
    op.drop_constraint("fk_search_events_category_id_categories", "search_events", type_="foreignkey")
    op.drop_constraint("fk_search_events_supplier_id_suppliers", "search_events", type_="foreignkey")
    op.drop_column("search_events", "results_page")
    op.drop_column("search_events", "rank_position")
    op.drop_column("search_events", "referrer")
    op.drop_column("search_events", "page_url")
    op.drop_column("search_events", "page_type")
    op.drop_column("search_events", "corrected_query")
    op.drop_column("search_events", "normalized_query")
    op.drop_column("search_events", "query_text")
    op.drop_column("search_events", "category_id")
    op.drop_column("search_events", "supplier_id")
    op.drop_column("search_events", "role")
