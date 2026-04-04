import threading

from app.db.repositories.catalog import CatalogRepository
from app.db.repositories.search import SearchRepository
from app.domain.catalog.schemas import (
    CatalogFeedItemRead,
    CatalogFeedRead,
    CatalogSummaryCategoryRead,
    CatalogSummaryRead,
    CategoryRead,
    PurchaseHistoryItemRead,
    RelatedSTEItemRead,
    SupplierInsightsRead,
    SupplierInsightCategoryRead,
    SupplierInsightOpportunityRead,
    SupplierInsightSupplierRead,
    STEItemRead,
    SearchableSTEItemRead,
    SupplierRead,
)
from app.domain.search.normalizer import extract_query_terms


class CatalogService:
    _cache_lock = threading.Lock()
    _categories_cache: tuple[CategoryRead, ...] | None = None
    _suppliers_cache: tuple[SupplierRead, ...] | None = None

    def __init__(
        self,
        repository: CatalogRepository,
        search_repository: SearchRepository,
    ) -> None:
        self.repository = repository
        self.search_repository = search_repository

    def list_categories(self) -> list[CategoryRead]:
        cache = self.__class__._categories_cache
        if cache is not None:
            return list(cache)

        with self.__class__._cache_lock:
            cache = self.__class__._categories_cache
            if cache is None:
                cache = tuple(
                    CategoryRead(
                        id=item.id,
                        name=item.name,
                        parent_id=item.parent_id,
                    )
                    for item in self.repository.list_categories()
                )
                self.__class__._categories_cache = cache
        return list(cache)

    def list_suppliers(self) -> list[SupplierRead]:
        cache = self.__class__._suppliers_cache
        if cache is not None:
            return list(cache)

        with self.__class__._cache_lock:
            cache = self.__class__._suppliers_cache
            if cache is None:
                cache = tuple(
                    SupplierRead(
                        id=item.id,
                        name=item.name,
                    )
                    for item in self.repository.list_suppliers()
                )
                self.__class__._suppliers_cache = cache
        return list(cache)

    def get_catalog_summary(self, user_id: str) -> CatalogSummaryRead:
        summary = self.repository.get_catalog_summary(user_id=user_id)
        return CatalogSummaryRead(
            ste_items_count=summary.ste_items_count,
            categories_count=summary.categories_count,
            suppliers_count=summary.suppliers_count,
            purchase_history_count=summary.purchase_history_count,
            favorites_count=summary.favorites_count,
            comparison_count=summary.comparison_count,
            cart_count=summary.cart_count,
            latest_item_updated_at=summary.latest_item_updated_at,
            top_categories=[
                CatalogSummaryCategoryRead(
                    id=item.id,
                    name=item.name,
                    item_count=item.item_count,
                )
                for item in summary.top_categories
            ],
        )

    def get_supplier_insights(self, organization_name: str) -> SupplierInsightsRead:
        insights = self.repository.get_supplier_insights(organization_name=organization_name)
        return SupplierInsightsRead(
            matched_suppliers=[
                SupplierInsightSupplierRead(
                    id=item.id,
                    name=item.name,
                    token_overlap=item.token_overlap,
                    catalog_items_count=item.catalog_items_count,
                    purchase_history_count=item.purchase_history_count,
                )
                for item in insights.matched_suppliers
            ],
            owned_catalog_items_count=insights.owned_catalog_items_count,
            owned_purchase_history_count=insights.owned_purchase_history_count,
            tracked_categories_count=insights.tracked_categories_count,
            top_demand_categories=[
                SupplierInsightCategoryRead(
                    id=item.id,
                    name=item.name,
                    purchase_count=item.purchase_count,
                    catalog_items_count=item.catalog_items_count,
                )
                for item in insights.top_demand_categories
            ],
            top_competitors=[
                SupplierInsightSupplierRead(
                    id=item.id,
                    name=item.name,
                    token_overlap=item.token_overlap,
                    catalog_items_count=item.catalog_items_count,
                    purchase_history_count=item.purchase_history_count,
                )
                for item in insights.top_competitors
            ],
            hot_opportunities=[
                SupplierInsightOpportunityRead(
                    ste_id=item.ste_id,
                    title=item.title,
                    supplier_name=item.supplier_name,
                    category_name=item.category_name,
                    purchase_count=item.purchase_count,
                )
                for item in insights.hot_opportunities
            ],
        )

    def list_ste_items(self) -> list[STEItemRead]:
        return [
            STEItemRead(
                id=item.id,
                title=item.title,
                description=item.description,
                category_id=item.category_id,
                category_name=item.category.name,
                supplier_id=item.supplier_id,
                supplier_name=item.supplier.name,
                attributes=item.attributes_json,
                status=item.status,
            )
            for item in self.repository.list_ste_items()
        ]

    def get_catalog_feed(
        self,
        *,
        user_id: str,
        organization_id: str,
        limit: int = 12,
        offset: int = 0,
        category_id: str | None = None,
        supplier_id: str | None = None,
    ) -> CatalogFeedRead:
        snapshot = self.repository.get_catalog_feed(
            user_id=user_id,
            organization_id=organization_id,
            limit=limit,
            offset=offset,
            category_id=category_id,
            supplier_id=supplier_id,
        )
        return CatalogFeedRead(
            items=[
                CatalogFeedItemRead(
                    id=item.item.id,
                    title=item.item.title,
                    description=item.item.description,
                    category_id=item.item.category_id,
                    category_name=item.item.category.name,
                    supplier_id=item.item.supplier_id,
                    supplier_name=item.item.supplier.name,
                    attributes=item.item.attributes_json,
                    status=item.item.status,
                    feed_reason=item.feed_reason,
                )
                for item in snapshot.items
            ],
            total=snapshot.total,
            limit=snapshot.limit,
            offset=snapshot.offset,
        )

    def search_ste_items(
        self,
        query_terms: list[str],
        morphology_query_terms: list[str] | None = None,
        fuzzy_query_terms: list[str] | None = None,
        synonym_query_terms: list[str] | None = None,
        semantic_query_texts: list[str] | None = None,
        structured_query=None,
        strict_match: bool = False,
        category_id: str | None = None,
        supplier_id: str | None = None,
        allowed_document_ids: set[str] | None = None,
        limit: int = 80,
    ) -> list[STEItemRead]:
        return [
            STEItemRead(
                id=item.id,
                title=item.title,
                description=item.description,
                category_id=item.category_id,
                category_name=item.category.name,
                supplier_id=item.supplier_id,
                supplier_name=item.supplier.name,
                attributes=item.attributes_json,
                status=item.status,
            )
            for item in (
                hit.item
                for hit in self.search_repository.search_candidates(
                    query_terms=query_terms,
                    morphology_query_terms=morphology_query_terms,
                    fuzzy_query_terms=fuzzy_query_terms,
                    synonym_query_terms=synonym_query_terms,
                    semantic_query_texts=semantic_query_texts,
                    structured_query=structured_query,
                    strict_match=strict_match,
                    category_id=category_id,
                    supplier_id=supplier_id,
                    allowed_document_ids=allowed_document_ids,
                    limit=limit,
                )
            )
        ]

    def search_ste_candidates(
        self,
        query_terms: list[str],
        morphology_query_terms: list[str] | None = None,
        fuzzy_query_terms: list[str] | None = None,
        synonym_query_terms: list[str] | None = None,
        semantic_query_texts: list[str] | None = None,
        structured_query=None,
        strict_match: bool = False,
        category_id: str | None = None,
        supplier_id: str | None = None,
        allowed_document_ids: set[str] | None = None,
        limit: int = 80,
    ) -> list[SearchableSTEItemRead]:
        return [
            SearchableSTEItemRead(
                id=hit.item.id,
                title=hit.item.title,
                description=hit.item.description,
                category_id=hit.item.category_id,
                category_name=hit.item.category.name,
                supplier_id=hit.item.supplier_id,
                supplier_name=hit.item.supplier.name,
                attributes=hit.item.attributes_json,
                status=hit.item.status,
                retrieval_score=hit.retrieval_score,
                retrieval_reasons=hit.retrieval_reasons,
                retrieval_channel_scores=hit.retrieval_channel_scores,
                retrieval_channel_ranks=hit.retrieval_channel_ranks,
                retrieval_features=hit.retrieval_features,
            )
            for hit in self.search_repository.search_candidates(
                query_terms=query_terms,
                morphology_query_terms=morphology_query_terms,
                fuzzy_query_terms=fuzzy_query_terms,
                synonym_query_terms=synonym_query_terms,
                semantic_query_texts=semantic_query_texts,
                structured_query=structured_query,
                strict_match=strict_match,
                category_id=category_id,
                supplier_id=supplier_id,
                allowed_document_ids=allowed_document_ids,
                limit=limit,
            )
        ]

    def get_ste_by_id(self, ste_id: str) -> STEItemRead | None:
        item = self.repository.get_ste_by_id(ste_id)
        if item is None:
            return None
        return STEItemRead(
            id=item.id,
            title=item.title,
            description=item.description,
            category_id=item.category_id,
            category_name=item.category.name,
            supplier_id=item.supplier_id,
            supplier_name=item.supplier.name,
            attributes=item.attributes_json,
            status=item.status,
        )

    def get_related_ste_items(
        self,
        ste_id: str,
        limit: int = 6,
    ) -> list[RelatedSTEItemRead]:
        current_item = self.repository.get_ste_by_id(ste_id)
        if current_item is None:
            return []

        current_terms = set(extract_query_terms(current_item.title))
        current_attributes = {value.lower() for value in current_item.attributes_json.values()}
        candidates = self.repository.list_related_candidates(
            ste_id=ste_id,
            category_id=current_item.category_id,
            supplier_id=current_item.supplier_id,
            limit=max(limit * 2, limit),
        )

        ranked_items: list[RelatedSTEItemRead] = []
        for item in candidates:
            score = 0.0
            reasons: list[str] = []

            if item.category_id == current_item.category_id:
                score += 0.4
                reasons.append("same_category")

            if item.supplier_id == current_item.supplier_id:
                score += 0.2
                reasons.append("same_supplier")

            candidate_terms = set(extract_query_terms(item.title))
            overlapping_terms = current_terms & candidate_terms
            if overlapping_terms:
                score += min(len(overlapping_terms) * 0.12, 0.24)
                reasons.append("title_overlap")

            candidate_attributes = {value.lower() for value in item.attributes_json.values()}
            overlapping_attributes = current_attributes & candidate_attributes
            if overlapping_attributes:
                score += min(len(overlapping_attributes) * 0.1, 0.2)
                reasons.append("attribute_overlap")

            if score <= 0:
                continue

            ranked_items.append(
                RelatedSTEItemRead(
                    id=item.id,
                    title=item.title,
                    description=item.description,
                    category_id=item.category_id,
                    category_name=item.category.name,
                    supplier_id=item.supplier_id,
                    supplier_name=item.supplier.name,
                    attributes=item.attributes_json,
                    status=item.status,
                    score=round(score, 4),
                    reasons=reasons,
                )
            )

        ranked_items.sort(key=lambda item: item.score, reverse=True)
        return ranked_items[:limit]

    def get_purchase_history(
        self,
        user_id: str,
        organization_id: str,
        limit: int = 6,
    ) -> list[PurchaseHistoryItemRead]:
        purchases = self.repository.list_purchase_history(
            user_id=user_id,
            organization_id=organization_id,
            limit=limit,
        )

        items: list[PurchaseHistoryItemRead] = []
        for purchase in purchases:
            ste_item = self.repository.get_ste_by_id(purchase.ste_id)
            if ste_item is None:
                continue

            items.append(
                PurchaseHistoryItemRead(
                    id=purchase.id,
                    ste_id=purchase.ste_id,
                    title=ste_item.title,
                    description=ste_item.description,
                    category_id=ste_item.category_id,
                    category_name=ste_item.category.name,
                    supplier_id=ste_item.supplier_id,
                    supplier_name=ste_item.supplier.name,
                    quantity=purchase.quantity,
                    price=purchase.price,
                    purchased_at=purchase.purchased_at,
                )
            )

        return items
