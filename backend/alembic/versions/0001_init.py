"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_table(
        "ste_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category_id", sa.String(length=64), nullable=False),
        sa.Column("supplier_id", sa.String(length=64), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ste_items_title", "ste_items", ["title"])
    op.create_index("ix_ste_items_category_id", "ste_items", ["category_id"])
    op.create_index("ix_ste_items_supplier_id", "ste_items", ["supplier_id"])
    op.create_table(
        "purchase_history",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("ste_id", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.String(length=32), nullable=False),
        sa.Column("price", sa.String(length=64), nullable=False),
        sa.Column("purchased_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ste_id"], ["ste_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_history_user_id", "purchase_history", ["user_id"])
    op.create_index(
        "ix_purchase_history_organization_id", "purchase_history", ["organization_id"]
    )
    op.create_index("ix_purchase_history_ste_id", "purchase_history", ["ste_id"])
    op.create_table(
        "search_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_sessions_user_id", "search_sessions", ["user_id"])
    op.create_index(
        "ix_search_sessions_organization_id", "search_sessions", ["organization_id"]
    )
    op.create_table(
        "search_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("ste_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["search_sessions.id"]),
        sa.ForeignKeyConstraint(["ste_id"], ["ste_items.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_search_events_session_id", "search_events", ["session_id"])
    op.create_index("ix_search_events_user_id", "search_events", ["user_id"])
    op.create_index(
        "ix_search_events_organization_id", "search_events", ["organization_id"]
    )
    op.create_index("ix_search_events_ste_id", "search_events", ["ste_id"])
    op.create_table(
        "synonyms",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("term", sa.String(length=255), nullable=False),
        sa.Column("synonym", sa.String(length=255), nullable=False),
        sa.Column("weight", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_synonyms_term", "synonyms", ["term"])
    op.create_index("ix_synonyms_synonym", "synonyms", ["synonym"])
    op.create_table(
        "user_search_profiles",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("top_categories_json", sa.JSON(), nullable=False),
        sa.Column("recent_ste_ids_json", sa.JSON(), nullable=False),
        sa.Column("top_suppliers_json", sa.JSON(), nullable=False),
        sa.Column("popular_queries_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "ix_user_search_profiles_organization_id",
        "user_search_profiles",
        ["organization_id"],
    )
    op.create_table(
        "org_search_profiles",
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("top_categories_json", sa.JSON(), nullable=False),
        sa.Column("popular_ste_ids_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def downgrade() -> None:
    op.drop_table("org_search_profiles")
    op.drop_index("ix_user_search_profiles_organization_id", table_name="user_search_profiles")
    op.drop_table("user_search_profiles")
    op.drop_index("ix_synonyms_synonym", table_name="synonyms")
    op.drop_index("ix_synonyms_term", table_name="synonyms")
    op.drop_table("synonyms")
    op.drop_index("ix_search_events_ste_id", table_name="search_events")
    op.drop_index("ix_search_events_organization_id", table_name="search_events")
    op.drop_index("ix_search_events_user_id", table_name="search_events")
    op.drop_index("ix_search_events_session_id", table_name="search_events")
    op.drop_table("search_events")
    op.drop_index("ix_search_sessions_organization_id", table_name="search_sessions")
    op.drop_index("ix_search_sessions_user_id", table_name="search_sessions")
    op.drop_table("search_sessions")
    op.drop_index("ix_purchase_history_ste_id", table_name="purchase_history")
    op.drop_index("ix_purchase_history_organization_id", table_name="purchase_history")
    op.drop_index("ix_purchase_history_user_id", table_name="purchase_history")
    op.drop_table("purchase_history")
    op.drop_index("ix_ste_items_supplier_id", table_name="ste_items")
    op.drop_index("ix_ste_items_category_id", table_name="ste_items")
    op.drop_index("ix_ste_items_title", table_name="ste_items")
    op.drop_table("ste_items")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_table("users")
    op.drop_table("suppliers")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")
    op.drop_table("organizations")
