from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), default="customer")

    organization: Mapped[OrganizationModel] = relationship()


class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, index=True
    )


class SupplierModel(Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class STEItemModel(Base):
    __tablename__ = "ste_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.id"), nullable=False, index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.id"), nullable=False, index=True
    )
    attributes_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="active")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    category: Mapped[CategoryModel] = relationship()
    supplier: Mapped[SupplierModel] = relationship()


class PurchaseHistoryModel(Base):
    __tablename__ = "purchase_history"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    ste_id: Mapped[str] = mapped_column(ForeignKey("ste_items.id"), index=True)
    quantity: Mapped[str] = mapped_column(String(32), default="1")
    price: Mapped[str] = mapped_column(String(64), default="0")
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SearchSessionModel(Base):
    __tablename__ = "search_sessions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SearchEventModel(Base):
    __tablename__ = "search_events"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("search_sessions.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(64), default="customer")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ste_id: Mapped[str | None] = mapped_column(
        ForeignKey("ste_items.id"), nullable=True, index=True
    )
    supplier_id: Mapped[str | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True, index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, index=True
    )
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rank_position: Mapped[int | None] = mapped_column(nullable=True)
    results_page: Mapped[int | None] = mapped_column(nullable=True)
    payload_json: Mapped[dict[str, str | int | float | bool]] = mapped_column(
        JSON, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SearchImpressionModel(Base):
    __tablename__ = "search_impressions"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    search_session_id: Mapped[str] = mapped_column(
        ForeignKey("search_sessions.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    ste_id: Mapped[str] = mapped_column(ForeignKey("ste_items.id"), index=True)
    supplier_id: Mapped[str | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True, index=True
    )
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, index=True
    )
    rank_position: Mapped[int] = mapped_column(nullable=False)
    results_page: Mapped[int] = mapped_column(default=1)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    rendered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FavoriteModel(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "ste_id", name="uq_favorites_user_ste"),)

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    ste_id: Mapped[str] = mapped_column(ForeignKey("ste_items.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ComparisonItemModel(Base):
    __tablename__ = "comparison_items"
    __table_args__ = (
        UniqueConstraint("user_id", "ste_id", name="uq_comparison_items_user_ste"),
    )

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    ste_id: Mapped[str] = mapped_column(ForeignKey("ste_items.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CartItemModel(Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("user_id", "ste_id", name="uq_cart_items_user_ste"),)

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    ste_id: Mapped[str] = mapped_column(ForeignKey("ste_items.id"), index=True)
    quantity: Mapped[str] = mapped_column(String(16), default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SynonymModel(Base):
    __tablename__ = "synonyms"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    term: Mapped[str] = mapped_column(String(255), index=True)
    synonym: Mapped[str] = mapped_column(String(255), index=True)
    weight: Mapped[str] = mapped_column(String(16), default="1.0")
    source: Mapped[str] = mapped_column(String(64), default="manual")


class SpellCorrectionModel(Base):
    __tablename__ = "spell_corrections"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: uuid4().hex
    )
    wrong_term: Mapped[str] = mapped_column(String(255), index=True)
    correct_term: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(64), default="manual")


class UserSearchProfileModel(Base):
    __tablename__ = "user_search_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, index=True
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), index=True
    )
    top_categories_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    recent_ste_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    top_suppliers_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    popular_queries_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrgSearchProfileModel(Base):
    __tablename__ = "org_search_profiles"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True, index=True
    )
    top_categories_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    popular_ste_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
