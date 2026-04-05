import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import String, Text, cast, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    CartItemModel,
    CategoryModel,
    ComparisonItemModel,
    FavoriteModel,
    PurchaseHistoryModel,
    STEItemModel,
    SupplierModel,
)
from app.domain.catalog.origin_filters import extract_origin_values, matches_origin_filters

TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9]+")
SUPPLIER_STOPWORDS = {"ооо", "ао", "оао", "зао", "ип", "fgup", "фгуп", "group", "trade"}


@dataclass
class CatalogSummaryTopCategory:
    id: str
    name: str
    item_count: int


@dataclass
class CatalogSummarySnapshot:
    ste_items_count: int
    categories_count: int
    suppliers_count: int
    purchase_history_count: int
    favorites_count: int
    comparison_count: int
    cart_count: int
    latest_item_updated_at: datetime | None
    top_categories: list[CatalogSummaryTopCategory]


@dataclass
class SupplierInsightSupplierSnapshot:
    id: str
    name: str
    token_overlap: int
    catalog_items_count: int
    purchase_history_count: int


@dataclass
class SupplierInsightCategorySnapshot:
    id: str
    name: str
    purchase_count: int
    catalog_items_count: int


@dataclass
class SupplierInsightOpportunitySnapshot:
    ste_id: str
    title: str
    supplier_name: str
    category_name: str
    purchase_count: int


@dataclass
class SupplierInsightsSnapshot:
    matched_suppliers: list[SupplierInsightSupplierSnapshot]
    owned_catalog_items_count: int
    owned_purchase_history_count: int
    tracked_categories_count: int
    top_demand_categories: list[SupplierInsightCategorySnapshot]
    top_competitors: list[SupplierInsightSupplierSnapshot]
    hot_opportunities: list[SupplierInsightOpportunitySnapshot]


@dataclass
class CatalogFeedItemSnapshot:
    item: STEItemModel
    feed_reason: str


@dataclass
class CatalogFeedSnapshot:
    items: list[CatalogFeedItemSnapshot]
    total: int
    limit: int
    offset: int


@dataclass
class ProductionOriginOptionSnapshot:
    value: str
    item_count: int


def _extract_tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_RE.findall(value.lower())
        if len(token) > 2 and token.lower() not in SUPPLIER_STOPWORDS
    }


class CatalogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_categories(self) -> list[CategoryModel]:
        return list(self.session.scalars(select(CategoryModel).order_by(CategoryModel.name)))

    def list_suppliers(self) -> list[SupplierModel]:
        return list(self.session.scalars(select(SupplierModel).order_by(SupplierModel.name)))

    def list_ste_items(self) -> list[STEItemModel]:
        stmt = select(STEItemModel).options(
            joinedload(STEItemModel.category),
            joinedload(STEItemModel.supplier),
        )
        return list(self.session.scalars(stmt))

    def get_catalog_feed(
        self,
        *,
        user_id: str,
        organization_id: str,
        limit: int = 12,
        offset: int = 0,
        category_id: str | None = None,
        supplier_id: str | None = None,
        domestic_only: bool = False,
        origin_value: str | None = None,
    ) -> CatalogFeedSnapshot:
        candidate_ids: list[str] = []
        reason_by_id: dict[str, str] = {}

        def push(items: list[tuple[str, str]]) -> None:
            for item_id, reason in items:
                if item_id in reason_by_id:
                    continue
                reason_by_id[item_id] = reason
                candidate_ids.append(item_id)

        favorites_stmt = (
            select(FavoriteModel.ste_id)
            .where(FavoriteModel.user_id == user_id)
            .order_by(FavoriteModel.created_at.desc())
            .limit(18)
        )
        push([(ste_id, "Из избранного и недавних сигналов") for ste_id in self.session.scalars(favorites_stmt)])

        cart_stmt = (
            select(CartItemModel.ste_id)
            .where(CartItemModel.user_id == user_id)
            .order_by(CartItemModel.updated_at.desc())
            .limit(18)
        )
        push([(ste_id, "Продолжение текущей подборки") for ste_id in self.session.scalars(cart_stmt)])

        purchases_stmt = (
            select(PurchaseHistoryModel.ste_id)
            .where(
                PurchaseHistoryModel.user_id == user_id,
                PurchaseHistoryModel.organization_id == organization_id,
            )
            .order_by(PurchaseHistoryModel.purchased_at.desc())
            .limit(24)
        )
        push([(ste_id, "Похоже на историю закупок") for ste_id in self.session.scalars(purchases_stmt)])

        popular_stmt = (
            select(PurchaseHistoryModel.ste_id, func.count(PurchaseHistoryModel.id).label("purchase_count"))
            .group_by(PurchaseHistoryModel.ste_id)
            .order_by(func.count(PurchaseHistoryModel.id).desc(), PurchaseHistoryModel.ste_id.asc())
            .limit(80)
        )
        push([(ste_id, "Популярно среди закупок") for ste_id, _ in self.session.execute(popular_stmt)])

        latest_stmt = select(STEItemModel.id).order_by(STEItemModel.updated_at.desc(), STEItemModel.id.asc()).limit(80)
        push([(ste_id, "Недавно обновлено в каталоге") for ste_id in self.session.scalars(latest_stmt)])

        if not candidate_ids:
            return CatalogFeedSnapshot(items=[], total=0, limit=limit, offset=offset)

        stmt = (
            select(STEItemModel)
            .where(STEItemModel.id.in_(candidate_ids))
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
        )
        if category_id:
            stmt = stmt.where(STEItemModel.category_id == category_id)
        if supplier_id:
            stmt = stmt.where(STEItemModel.supplier_id == supplier_id)

        items = list(self.session.scalars(stmt))
        if domestic_only or origin_value:
            items = [
                item
                for item in items
                if matches_origin_filters(
                    item.attributes_json,
                    domestic_only=domestic_only,
                    origin_value=origin_value,
                )
            ]
        order = {item_id: index for index, item_id in enumerate(candidate_ids)}
        items.sort(key=lambda item: order.get(item.id, len(order)))

        total = len(items)
        paged_items = items[offset : offset + limit]
        snapshots = [
            CatalogFeedItemSnapshot(
                item=item,
                feed_reason=reason_by_id.get(item.id, "Подобрано для стартовой ленты"),
            )
            for item in paged_items
        ]
        return CatalogFeedSnapshot(items=snapshots, total=total, limit=limit, offset=offset)

    def list_production_origins(self, limit: int = 120) -> list[ProductionOriginOptionSnapshot]:
        counter: dict[str, int] = {}
        stmt = select(STEItemModel.attributes_json)
        for attributes in self.session.scalars(stmt):
            for value in extract_origin_values(attributes):
                counter[value] = counter.get(value, 0) + 1

        ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
        return [
            ProductionOriginOptionSnapshot(value=value, item_count=item_count)
            for value, item_count in ranked[:limit]
        ]

    def get_ste_by_id(self, ste_id: str) -> STEItemModel | None:
        stmt = (
            select(STEItemModel)
            .where(STEItemModel.id == ste_id)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
        )
        return self.session.scalar(stmt)

    def list_related_candidates(
        self,
        ste_id: str,
        category_id: str,
        supplier_id: str,
        limit: int = 12,
    ) -> list[STEItemModel]:
        stmt = (
            select(STEItemModel)
            .where(
                STEItemModel.id != ste_id,
                or_(
                    STEItemModel.category_id == category_id,
                    STEItemModel.supplier_id == supplier_id,
                ),
            )
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def search_ste_items(
        self,
        query: str,
        strict_match: bool = False,
        category_id: str | None = None,
        supplier_id: str | None = None,
    ) -> list[STEItemModel]:
        stmt = select(STEItemModel).options(
            joinedload(STEItemModel.category),
            joinedload(STEItemModel.supplier),
        )

        if query:
            pattern = query if strict_match else f"%{query}%"
            stmt = stmt.where(
                or_(
                    STEItemModel.title.ilike(pattern),
                    STEItemModel.description.ilike(pattern),
                    cast(STEItemModel.attributes_json, Text).ilike(pattern),
                    cast(STEItemModel.category_id, String).ilike(pattern),
                )
            )

        if category_id:
            stmt = stmt.where(STEItemModel.category_id == category_id)

        if supplier_id:
            stmt = stmt.where(STEItemModel.supplier_id == supplier_id)

        return list(self.session.scalars(stmt))

    def list_purchase_history(
        self,
        user_id: str,
        organization_id: str,
        limit: int = 6,
    ) -> list[PurchaseHistoryModel]:
        stmt = (
            select(PurchaseHistoryModel)
            .where(
                PurchaseHistoryModel.user_id == user_id,
                PurchaseHistoryModel.organization_id == organization_id,
            )
            .order_by(PurchaseHistoryModel.purchased_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def get_catalog_summary(self, user_id: str) -> CatalogSummarySnapshot:
        ste_items_count = self.session.scalar(select(func.count(STEItemModel.id))) or 0
        categories_count = self.session.scalar(select(func.count(CategoryModel.id))) or 0
        suppliers_count = self.session.scalar(select(func.count(SupplierModel.id))) or 0
        purchase_history_count = (
            self.session.scalar(select(func.count(PurchaseHistoryModel.id))) or 0
        )
        favorites_count = (
            self.session.scalar(
                select(func.count(FavoriteModel.id)).where(FavoriteModel.user_id == user_id)
            )
            or 0
        )
        comparison_count = (
            self.session.scalar(
                select(func.count(ComparisonItemModel.id)).where(
                    ComparisonItemModel.user_id == user_id
                )
            )
            or 0
        )
        cart_count = (
            self.session.scalar(
                select(func.count(CartItemModel.id)).where(CartItemModel.user_id == user_id)
            )
            or 0
        )
        latest_item_updated_at = self.session.scalar(select(func.max(STEItemModel.updated_at)))

        top_categories_stmt = (
            select(
                CategoryModel.id,
                CategoryModel.name,
                func.count(STEItemModel.id).label("item_count"),
            )
            .join(STEItemModel, STEItemModel.category_id == CategoryModel.id)
            .group_by(CategoryModel.id, CategoryModel.name)
            .order_by(func.count(STEItemModel.id).desc(), CategoryModel.name.asc())
            .limit(6)
        )
        top_categories = [
            CatalogSummaryTopCategory(
                id=category_id,
                name=name,
                item_count=item_count,
            )
            for category_id, name, item_count in self.session.execute(top_categories_stmt)
        ]

        return CatalogSummarySnapshot(
            ste_items_count=int(ste_items_count),
            categories_count=int(categories_count),
            suppliers_count=int(suppliers_count),
            purchase_history_count=int(purchase_history_count),
            favorites_count=int(favorites_count),
            comparison_count=int(comparison_count),
            cart_count=int(cart_count),
            latest_item_updated_at=latest_item_updated_at,
            top_categories=top_categories,
        )

    def get_supplier_insights(self, organization_name: str) -> SupplierInsightsSnapshot:
        organization_tokens = _extract_tokens(organization_name)
        suppliers = list(self.session.scalars(select(SupplierModel).order_by(SupplierModel.name)))
        matched_suppliers = []
        for supplier in suppliers:
            supplier_tokens = _extract_tokens(supplier.name)
            overlap = len(organization_tokens & supplier_tokens)
            if overlap <= 0:
                continue
            matched_suppliers.append((supplier, overlap))

        matched_suppliers.sort(key=lambda item: (-item[1], item[0].name))
        matched_suppliers = matched_suppliers[:6]
        matched_supplier_ids = [item.id for item, _ in matched_suppliers]

        if not matched_supplier_ids:
            return SupplierInsightsSnapshot(
                matched_suppliers=[],
                owned_catalog_items_count=0,
                owned_purchase_history_count=0,
                tracked_categories_count=0,
                top_demand_categories=[],
                top_competitors=[],
                hot_opportunities=[],
            )

        own_supplier_counts_stmt = (
            select(
                SupplierModel.id,
                SupplierModel.name,
                func.count(func.distinct(STEItemModel.id)).label("catalog_items_count"),
                func.count(PurchaseHistoryModel.id).label("purchase_history_count"),
            )
            .join(STEItemModel, STEItemModel.supplier_id == SupplierModel.id)
            .outerjoin(PurchaseHistoryModel, PurchaseHistoryModel.ste_id == STEItemModel.id)
            .where(SupplierModel.id.in_(matched_supplier_ids))
            .group_by(SupplierModel.id, SupplierModel.name)
        )
        own_supplier_counts = {
            supplier_id: SupplierInsightSupplierSnapshot(
                id=supplier_id,
                name=name,
                token_overlap=next(overlap for supplier, overlap in matched_suppliers if supplier.id == supplier_id),
                catalog_items_count=int(catalog_items_count),
                purchase_history_count=int(purchase_history_count),
            )
            for supplier_id, name, catalog_items_count, purchase_history_count in self.session.execute(
                own_supplier_counts_stmt
            )
        }

        owned_items_stmt = select(STEItemModel.id, STEItemModel.category_id).where(
            STEItemModel.supplier_id.in_(matched_supplier_ids)
        )
        owned_items = list(self.session.execute(owned_items_stmt))
        owned_item_ids = [item_id for item_id, _ in owned_items]
        owned_category_ids = sorted({category_id for _, category_id in owned_items})

        if not owned_category_ids:
            return SupplierInsightsSnapshot(
                matched_suppliers=list(own_supplier_counts.values()),
                owned_catalog_items_count=len(owned_item_ids),
                owned_purchase_history_count=sum(
                    item.purchase_history_count for item in own_supplier_counts.values()
                ),
                tracked_categories_count=0,
                top_demand_categories=[],
                top_competitors=[],
                hot_opportunities=[],
            )

        top_demand_categories_stmt = (
            select(
                CategoryModel.id,
                CategoryModel.name,
                func.count(PurchaseHistoryModel.id).label("purchase_count"),
                func.count(func.distinct(STEItemModel.id)).label("catalog_items_count"),
            )
            .join(STEItemModel, STEItemModel.category_id == CategoryModel.id)
            .outerjoin(PurchaseHistoryModel, PurchaseHistoryModel.ste_id == STEItemModel.id)
            .where(STEItemModel.category_id.in_(owned_category_ids))
            .group_by(CategoryModel.id, CategoryModel.name)
            .order_by(func.count(PurchaseHistoryModel.id).desc(), func.count(func.distinct(STEItemModel.id)).desc())
            .limit(6)
        )
        top_demand_categories = [
            SupplierInsightCategorySnapshot(
                id=category_id,
                name=name,
                purchase_count=int(purchase_count),
                catalog_items_count=int(catalog_items_count),
            )
            for category_id, name, purchase_count, catalog_items_count in self.session.execute(
                top_demand_categories_stmt
            )
        ]

        competitor_stmt = (
            select(
                SupplierModel.id,
                SupplierModel.name,
                func.count(func.distinct(STEItemModel.id)).label("catalog_items_count"),
                func.count(PurchaseHistoryModel.id).label("purchase_history_count"),
            )
            .join(STEItemModel, STEItemModel.supplier_id == SupplierModel.id)
            .outerjoin(PurchaseHistoryModel, PurchaseHistoryModel.ste_id == STEItemModel.id)
            .where(
                STEItemModel.category_id.in_(owned_category_ids),
                ~SupplierModel.id.in_(matched_supplier_ids),
            )
            .group_by(SupplierModel.id, SupplierModel.name)
            .order_by(func.count(PurchaseHistoryModel.id).desc(), func.count(func.distinct(STEItemModel.id)).desc())
            .limit(6)
        )
        top_competitors = [
            SupplierInsightSupplierSnapshot(
                id=supplier_id,
                name=name,
                token_overlap=0,
                catalog_items_count=int(catalog_items_count),
                purchase_history_count=int(purchase_history_count),
            )
            for supplier_id, name, catalog_items_count, purchase_history_count in self.session.execute(
                competitor_stmt
            )
        ]

        opportunities_stmt = (
            select(
                STEItemModel.id,
                STEItemModel.title,
                SupplierModel.name,
                CategoryModel.name,
                func.count(PurchaseHistoryModel.id).label("purchase_count"),
            )
            .join(PurchaseHistoryModel, PurchaseHistoryModel.ste_id == STEItemModel.id)
            .join(SupplierModel, SupplierModel.id == STEItemModel.supplier_id)
            .join(CategoryModel, CategoryModel.id == STEItemModel.category_id)
            .where(
                STEItemModel.category_id.in_(owned_category_ids),
                ~STEItemModel.supplier_id.in_(matched_supplier_ids),
            )
            .group_by(STEItemModel.id, STEItemModel.title, SupplierModel.name, CategoryModel.name)
            .order_by(func.count(PurchaseHistoryModel.id).desc(), STEItemModel.title.asc())
            .limit(6)
        )
        hot_opportunities = [
            SupplierInsightOpportunitySnapshot(
                ste_id=ste_id,
                title=title,
                supplier_name=supplier_name,
                category_name=category_name,
                purchase_count=int(purchase_count),
            )
            for ste_id, title, supplier_name, category_name, purchase_count in self.session.execute(
                opportunities_stmt
            )
        ]

        return SupplierInsightsSnapshot(
            matched_suppliers=[
                own_supplier_counts.get(
                    supplier.id,
                    SupplierInsightSupplierSnapshot(
                        id=supplier.id,
                        name=supplier.name,
                        token_overlap=overlap,
                        catalog_items_count=0,
                        purchase_history_count=0,
                    ),
                )
                for supplier, overlap in matched_suppliers
            ],
            owned_catalog_items_count=len(owned_item_ids),
            owned_purchase_history_count=sum(
                item.purchase_history_count for item in own_supplier_counts.values()
            ),
            tracked_categories_count=len(owned_category_ids),
            top_demand_categories=top_demand_categories,
            top_competitors=top_competitors,
            hot_opportunities=hot_opportunities,
        )
