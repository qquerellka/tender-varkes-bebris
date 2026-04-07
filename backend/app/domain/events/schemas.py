from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

EventType = Literal[
    "search_submitted",
    "search_results_rendered",
    "search_impression",
    "suggestion_clicked",
    "result_clicked",
    "result_opened",
    "result_opened_new_tab",
    "product_view_started",
    "product_view_ended",
    "item_copy",
    "favorite_added",
    "favorite_removed",
    "comparison_added",
    "comparison_removed",
    "cart_added",
    "cart_removed",
    "cart_quantity_changed",
    "filter_applied",
    "filter_removed",
    "filters_cleared",
    "sort_changed",
    "purchase_completed",
    "quick_back",
    "scroll_depth_changed",
    "search_refined",
    "search_abandoned",
    "purchase_intent",
    "irrelevant_marked",
]


class SearchEventCreate(BaseModel):
    session_id: str
    event_type: EventType
    ste_id: str | None = None
    supplier_id: str | None = None
    category_id: str | None = None
    query_text: str | None = None
    normalized_query: str | None = None
    corrected_query: str | None = None
    page_type: str | None = None
    page_url: str | None = None
    referrer: str | None = None
    rank_position: int | None = None
    results_page: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class SearchEventBatchCreate(BaseModel):
    items: list[SearchEventCreate] = Field(default_factory=list)


class SearchImpressionCreate(BaseModel):
    search_session_id: str
    ste_id: str
    supplier_id: str | None = None
    category_id: str | None = None
    rank_position: int = Field(ge=1)
    results_page: int = Field(default=1, ge=1)
    visible: bool = True


class SearchImpressionBatchCreate(BaseModel):
    items: list[SearchImpressionCreate] = Field(default_factory=list)


class EventBatchResult(BaseModel):
    created_count: int


class SearchEventRead(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    session_id: str
    user_id: str
    organization_id: str
    role: str
    event_type: EventType
    ste_id: str | None = None
    supplier_id: str | None = None
    category_id: str | None = None
    query_text: str | None = None
    normalized_query: str | None = None
    corrected_query: str | None = None
    page_type: str | None = None
    page_url: str | None = None
    referrer: str | None = None
    rank_position: int | None = None
    results_page: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SearchImpressionRead(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    search_session_id: str
    user_id: str
    organization_id: str
    ste_id: str
    supplier_id: str | None = None
    category_id: str | None = None
    rank_position: int
    results_page: int
    visible: bool = True
    rendered_at: datetime = Field(default_factory=datetime.utcnow)


class SearchEventListRead(BaseModel):
    items: list[SearchEventRead] = Field(default_factory=list)
    total: int


class SearchImpressionListRead(BaseModel):
    items: list[SearchImpressionRead] = Field(default_factory=list)
    total: int


class TelemetryCountByTypeRead(BaseModel):
    key: str
    count: int


class TelemetryHealthRead(BaseModel):
    user_id: str
    search_session_id: str | None = None
    search_sessions_count: int
    events_count: int
    impressions_count: int
    result_clicked_count: int
    result_opened_count: int
    purchase_intent_count: int
    purchase_completed_count: int
    search_sessions_with_impressions_count: int
    search_sessions_without_impressions_count: int
    click_through_rate: float
    open_after_click_rate: float
    purchase_after_intent_rate: float
    event_counts: list[TelemetryCountByTypeRead] = Field(default_factory=list)
