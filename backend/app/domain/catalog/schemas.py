from datetime import datetime

from pydantic import BaseModel, Field


class CategoryRead(BaseModel):
    id: str
    name: str
    parent_id: str | None = None


class SupplierRead(BaseModel):
    id: str
    name: str


class CatalogSummaryCategoryRead(BaseModel):
    id: str
    name: str
    item_count: int


class CatalogSummaryRead(BaseModel):
    ste_items_count: int
    categories_count: int
    suppliers_count: int
    purchase_history_count: int
    favorites_count: int
    comparison_count: int
    cart_count: int
    latest_item_updated_at: datetime | None = None
    top_categories: list[CatalogSummaryCategoryRead] = Field(default_factory=list)


class SupplierInsightSupplierRead(BaseModel):
    id: str
    name: str
    token_overlap: int
    catalog_items_count: int
    purchase_history_count: int


class SupplierInsightCategoryRead(BaseModel):
    id: str
    name: str
    purchase_count: int
    catalog_items_count: int


class SupplierInsightOpportunityRead(BaseModel):
    ste_id: str
    title: str
    supplier_name: str
    category_name: str
    purchase_count: int


class SupplierInsightsRead(BaseModel):
    matched_suppliers: list[SupplierInsightSupplierRead] = Field(default_factory=list)
    owned_catalog_items_count: int
    owned_purchase_history_count: int
    tracked_categories_count: int
    top_demand_categories: list[SupplierInsightCategoryRead] = Field(default_factory=list)
    top_competitors: list[SupplierInsightSupplierRead] = Field(default_factory=list)
    hot_opportunities: list[SupplierInsightOpportunityRead] = Field(default_factory=list)


class STEItemRead(BaseModel):
    id: str
    title: str
    description: str
    category_id: str
    category_name: str
    supplier_id: str
    supplier_name: str
    attributes: dict[str, str] = Field(default_factory=dict)
    attributes_text: str = Field(default="", exclude=True)
    attribute_value_count: int = Field(default=0, exclude=True)
    status: str


class SearchableSTEItemRead(STEItemRead):
    retrieval_score: float = 0.0
    retrieval_reasons: list[str] = Field(default_factory=list)
    retrieval_channel_scores: dict[str, float] = Field(default_factory=dict)
    retrieval_channel_ranks: dict[str, int] = Field(default_factory=dict)
    retrieval_features: dict[str, float] = Field(default_factory=dict)


class RelatedSTEItemRead(STEItemRead):
    score: float
    reasons: list[str] = Field(default_factory=list)


class PurchaseHistoryItemRead(BaseModel):
    id: str
    ste_id: str
    title: str
    description: str
    category_id: str
    category_name: str
    supplier_id: str
    supplier_name: str
    quantity: str
    price: str
    purchased_at: datetime


class CatalogFeedItemRead(STEItemRead):
    feed_reason: str


class CatalogFeedRead(BaseModel):
    items: list[CatalogFeedItemRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
