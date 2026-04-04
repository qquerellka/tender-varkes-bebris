from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.personalization.schemas import SearchProfileRead


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


class SearchQueryVariantRead(BaseModel):
    query: str
    source: str
    confidence: str
    is_primary: bool = False


class SearchMeta(BaseModel):
    session_id: str | None = None
    query: str
    normalized_query: str
    corrected_query: str | None = None
    correction_confidence: str = "none"
    applied_synonyms: list[str] = Field(default_factory=list)
    synonym_sources: dict[str, str] = Field(default_factory=dict)
    synonym_confidence: dict[str, float] = Field(default_factory=dict)
    query_variants: list[SearchQueryVariantRead] = Field(default_factory=list)
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
    correction_confidence: str = "none"
    query_variants: list[SearchQueryVariantRead] = Field(default_factory=list)


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


class SearchActivityItemRead(BaseModel):
    id: str
    session_id: str
    event_type: str
    title: str
    description: str
    ste_id: str | None = None
    ste_title: str | None = None
    page_type: str | None = None
    query: str | None = None
    created_at: datetime


class SearchActivityResponse(BaseModel):
    items: list[SearchActivityItemRead] = Field(default_factory=list)


class SearchDebugStructuredQueryRead(BaseModel):
    normalized_text: str
    text_terms: list[str] = Field(default_factory=list)
    lemma_terms: list[str] = Field(default_factory=list)
    brand_terms: list[str] = Field(default_factory=list)
    model_terms: list[str] = Field(default_factory=list)
    code_terms: list[str] = Field(default_factory=list)
    numeric_terms: list[str] = Field(default_factory=list)
    unit_terms: list[str] = Field(default_factory=list)
    size_terms: list[str] = Field(default_factory=list)
    package_terms: list[str] = Field(default_factory=list)
    color_terms: list[str] = Field(default_factory=list)
    material_terms: list[str] = Field(default_factory=list)
    category_hints: list[str] = Field(default_factory=list)
    attribute_terms: list[str] = Field(default_factory=list)
    quantity_constraints: list[str] = Field(default_factory=list)
    is_hard_query: bool = False


class SearchDebugQueryRead(BaseModel):
    original: str
    normalized: str
    effective: str
    corrected: str | None = None
    correction_type: str = "none"
    correction_confidence: str = "none"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    applied_synonyms: list[str] = Field(default_factory=list)
    synonym_sources: dict[str, str] = Field(default_factory=dict)
    synonym_confidence: dict[str, float] = Field(default_factory=dict)
    query_variants: list[SearchQueryVariantRead] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    morphology_terms: list[str] = Field(default_factory=list)
    synonym_terms: list[str] = Field(default_factory=list)
    fuzzy_terms: list[str] = Field(default_factory=list)
    semantic_query_texts: list[str] = Field(default_factory=list)
    ranking_query_terms: list[str] = Field(default_factory=list)
    structured_query: SearchDebugStructuredQueryRead


class SearchDebugCandidateRead(BaseModel):
    id: str
    title: str
    category: str
    supplier: str
    category_id: str
    supplier_id: str
    status: str
    baseline_score: float
    retrieval_score: float
    final_score: float
    score_delta: float
    baseline_rank: int
    final_rank: int
    baseline_reasons: list[str] = Field(default_factory=list)
    final_reasons: list[str] = Field(default_factory=list)
    retrieval_reasons: list[str] = Field(default_factory=list)
    retrieval_channel_scores: dict[str, float] = Field(default_factory=dict)
    retrieval_channel_ranks: dict[str, int] = Field(default_factory=dict)
    retrieval_features: dict[str, float] = Field(default_factory=dict)


class SearchDebugRankingRead(BaseModel):
    provider_name: str
    provider_mode: str
    provider_ready: bool = True
    model_type: str | None = None
    ml_rerank_applied: bool = False
    fallback_to_baseline: bool = False
    raw_candidates_count: int = 0
    scored_candidates_count: int = 0


class SearchDebugResponse(BaseModel):
    query: SearchDebugQueryRead
    profile: SearchProfileRead
    ranking: SearchDebugRankingRead
    candidates: list[SearchDebugCandidateRead] = Field(default_factory=list)


class SpellcheckResponse(BaseModel):
    original_query: str
    corrected_query: str | None = None
    correction_type: str = "none"
    correction_confidence: str = "none"
    query_variants: list[SearchQueryVariantRead] = Field(default_factory=list)


class SearchStackStatusRead(BaseModel):
    ready: bool
    search_warmup: str
    ranking_warmup: str
    search_warmup_duration_seconds: float | None = None
    ranking_warmup_duration_seconds: float | None = None
    ranking_provider: str | None = None
    ranking_provider_mode: str | None = None
    search_documents_count: int | None = None
    semantic_backend: str | None = None
    semantic_faiss_enabled: bool | None = None
    search_warmup_error: str | None = None
    ranking_warmup_error: str | None = None
