from datetime import datetime

from pydantic import BaseModel, Field


class CurrentActor(BaseModel):
    user_id: str
    organization_id: str
    role: str = "customer"
    name: str | None = None
    organization_name: str | None = None
    personalization_enabled: bool = True


class SearchFilters(BaseModel):
    category_id: str | None = None
    supplier_id: str | None = None
    strict_match: bool = False


class SearchRequest(BaseModel):
    query: str
    filters: SearchFilters = Field(default_factory=SearchFilters)


class CandidateItem(BaseModel):
    id: str
    title: str
    category: str
    supplier: str
    description: str
    score: float
    reasons: list[str] = Field(default_factory=list)
    category_id: str = Field(default="", exclude=True)
    supplier_id: str = Field(default="", exclude=True)
    status: str = Field(default="", exclude=True)
    attributes: dict[str, str] = Field(default_factory=dict, exclude=True)
    baseline_score: float = Field(default=0.0, exclude=True)
    retrieval_score: float = Field(default=0.0, exclude=True)
    retrieval_reasons: list[str] = Field(default_factory=list, exclude=True)
    retrieval_channel_scores: dict[str, float] = Field(default_factory=dict, exclude=True)
    retrieval_channel_ranks: dict[str, int] = Field(default_factory=dict, exclude=True)
    retrieval_features: dict[str, float] = Field(default_factory=dict, exclude=True)


class SearchMeta(BaseModel):
    session_id: str | None = None
    query: str
    normalized_query: str
    corrected_query: str | None = None
    applied_synonyms: list[str] = Field(default_factory=list)
    synonym_sources: dict[str, str] = Field(default_factory=dict)
    synonym_confidence: dict[str, float] = Field(default_factory=dict)
    explanations: list[str] = Field(default_factory=list)
    ranking_mode: str


class SearchResponse(BaseModel):
    items: list[CandidateItem]
    meta: SearchMeta


class SearchSuggestion(BaseModel):
    label: str
    type: str
    group: str
    description: str | None = None


class SearchSuggestionsMeta(BaseModel):
    query: str
    normalized_query: str
    effective_query: str
    corrected_query: str | None = None
    correction_type: str = "none"


class SearchSuggestionsResponse(BaseModel):
    items: list[SearchSuggestion] = Field(default_factory=list)
    meta: SearchSuggestionsMeta


class SearchSessionRead(BaseModel):
    id: str
    query: str
    normalized_query: str
    created_at: datetime


class SearchHistoryResponse(BaseModel):
    items: list[SearchSessionRead] = Field(default_factory=list)


class SpellcheckResponse(BaseModel):
    original_query: str
    corrected_query: str | None = None
