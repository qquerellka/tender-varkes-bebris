import logging
import pickle
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CategoryModel,
    STEItemModel,
    SearchSessionModel,
    SpellCorrectionModel,
    SupplierModel,
    SynonymModel,
)
from app.domain.catalog.origin_filters import matches_origin_filters
from app.domain.search.normalizer import (
    SpellVocabularyIndex,
    build_spell_vocabulary_index,
    extract_query_terms,
    normalize_query,
)
from app.domain.search.query_analysis import SearchTextAnalysis
from app.domain.search.retrieval import (
    CHANNEL_REASON_MAP,
    CHANNEL_RRF_WEIGHTS,
    HybridSearchIndex,
    RETRIEVAL_MAX_CANDIDATE_POOL,
    RETRIEVAL_MIN_CANDIDATE_POOL,
    SearchDocument,
)

LOGGER = logging.getLogger(__name__)
POSTGRES_RETRIEVAL_BACKEND = "postgres"
MEMORY_RETRIEVAL_BACKEND = "memory"
POSTGRES_FTS_MIN_SCORE = 0.01
POSTGRES_TRGM_MIN_SCORE = 0.08
POSTGRES_SEARCH_VECTOR_SQL = (
    "to_tsvector("
    "'simple', "
    "coalesce(ste.title, '') || ' ' || "
    "coalesce(ste.description, '') || ' ' || "
    "coalesce(CAST(ste.attributes_json AS text), '')"
    ")"
)
POSTGRES_TRGM_SCORE_SQL = (
    "similarity(ste.title, :query_text) * 1.2"
)


@dataclass(slots=True)
class SearchItemSnapshot:
    id: str
    title: str
    description: str
    category_id: str
    category_name: str
    supplier_id: str
    supplier_name: str
    attributes: dict[str, str] = field(default_factory=dict)
    attributes_text: str = ""
    attribute_value_count: int = 0
    status: str = "active"


@dataclass(slots=True)
class SearchCandidateRef:
    document_id: str
    retrieval_score: float = 0.0
    retrieval_reasons: list[str] = field(default_factory=list)
    retrieval_channel_scores: dict[str, float] = field(default_factory=dict)
    retrieval_channel_ranks: dict[str, int] = field(default_factory=dict)
    retrieval_features: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class SearchCandidateHit:
    item: SearchItemSnapshot
    retrieval_score: float = 0.0
    retrieval_reasons: list[str] = field(default_factory=list)
    retrieval_channel_scores: dict[str, float] = field(default_factory=dict)
    retrieval_channel_ranks: dict[str, int] = field(default_factory=dict)
    retrieval_features: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class SynonymExpansion:
    term: str
    synonym: str
    weight: float
    source: str


class SearchRepository:
    _INDEX_CACHE_FORMAT_VERSION = 2
    _hybrid_index_lock = threading.Lock()
    _search_vocabulary_cache: set[str] | None = None
    _search_spell_vocabulary_cache: SpellVocabularyIndex | None = None
    _search_vocabulary_pattern = re.compile(r"[0-9a-zа-яё]+", flags=re.IGNORECASE)
    _hybrid_index_cache: HybridSearchIndex | None = None
    _hybrid_index_signature: tuple[int, datetime | None] | None = None

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _get_retrieval_backend() -> str:
        backend = settings.search_retrieval_backend.strip().lower()
        if backend == POSTGRES_RETRIEVAL_BACKEND:
            return POSTGRES_RETRIEVAL_BACKEND
        return MEMORY_RETRIEVAL_BACKEND

    def warmup_search_backend(self) -> dict[str, Any]:
        if self._get_retrieval_backend() == POSTGRES_RETRIEVAL_BACKEND:
            document_count = self.session.scalar(select(func.count(STEItemModel.id))) or 0
            return {
                "documents_count": int(document_count),
                "semantic_backend": "disabled",
                "semantic_faiss_enabled": False,
            }

        index = self._get_hybrid_index()
        return {
            "documents_count": len(index.documents),
            "semantic_backend": index._semantic_backend,
            "semantic_faiss_enabled": index._semantic_faiss_index is not None,
        }

    def create_session(
        self,
        user_id: str,
        organization_id: str,
        query: str,
        normalized_query: str,
    ) -> SearchSessionModel:
        model = SearchSessionModel(
            user_id=user_id,
            organization_id=organization_id,
            query=query,
            normalized_query=normalized_query,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model

    def list_sessions(
        self,
        user_id: str,
        organization_id: str,
        limit: int = 20,
    ) -> list[SearchSessionModel]:
        stmt = (
            select(SearchSessionModel)
            .where(
                SearchSessionModel.user_id == user_id,
                SearchSessionModel.organization_id == organization_id,
            )
            .order_by(SearchSessionModel.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def clear_sessions(
        self,
        *,
        user_id: str,
        organization_id: str,
    ) -> int:
        deleted = self.session.execute(
            delete(SearchSessionModel).where(
                SearchSessionModel.user_id == user_id,
                SearchSessionModel.organization_id == organization_id,
            )
        )
        self.session.commit()
        return deleted.rowcount or 0

    def search_candidates(
        self,
        query_terms: list[str],
        query_text_variants: list[str] | None = None,
        morphology_query_terms: list[str] | None = None,
        fuzzy_query_terms: list[str] | None = None,
        synonym_query_terms: list[str] | None = None,
        semantic_query_texts: list[str] | None = None,
        structured_query: SearchTextAnalysis | None = None,
        strict_match: bool = False,
        category_id: str | None = None,
        supplier_id: str | None = None,
        domestic_only: bool = False,
        origin_value: str | None = None,
        allowed_document_ids: set[str] | None = None,
        limit: int = 80,
    ) -> list[SearchCandidateHit]:
        retrieval_refs = self.search_candidate_refs(
            query_terms=query_terms,
            query_text_variants=query_text_variants,
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
        if not retrieval_refs:
            return []

        items_by_id = self.load_search_item_snapshots(
            [result.document_id for result in retrieval_refs]
        )

        hits: list[SearchCandidateHit] = []
        for result in retrieval_refs:
            item = items_by_id.get(result.document_id)
            if item is None:
                continue
            if not matches_origin_filters(
                item.attributes,
                domestic_only=domestic_only,
                origin_value=origin_value,
            ):
                continue
            hits.append(
                SearchCandidateHit(
                    item=item,
                    retrieval_score=result.retrieval_score,
                    retrieval_reasons=result.retrieval_reasons or ["retrieval_rrf"],
                    retrieval_channel_scores=result.retrieval_channel_scores,
                    retrieval_channel_ranks=result.retrieval_channel_ranks,
                    retrieval_features=result.retrieval_features,
                )
            )
        return hits

    def search_candidate_refs(
        self,
        query_terms: list[str],
        query_text_variants: list[str] | None = None,
        morphology_query_terms: list[str] | None = None,
        fuzzy_query_terms: list[str] | None = None,
        synonym_query_terms: list[str] | None = None,
        semantic_query_texts: list[str] | None = None,
        structured_query: SearchTextAnalysis | None = None,
        strict_match: bool = False,
        category_id: str | None = None,
        supplier_id: str | None = None,
        allowed_document_ids: set[str] | None = None,
        limit: int = 80,
    ) -> list[SearchCandidateRef]:
        if self._get_retrieval_backend() == POSTGRES_RETRIEVAL_BACKEND:
            return self._search_candidate_refs_postgres(
                query_terms=query_terms,
                query_text_variants=query_text_variants,
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

        return self._search_candidate_refs_memory(
            query_terms=query_terms,
            query_text_variants=query_text_variants,
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

    def _search_candidate_refs_memory(
        self,
        query_terms: list[str],
        query_text_variants: list[str] | None = None,
        morphology_query_terms: list[str] | None = None,
        fuzzy_query_terms: list[str] | None = None,
        synonym_query_terms: list[str] | None = None,
        semantic_query_texts: list[str] | None = None,
        structured_query: SearchTextAnalysis | None = None,
        strict_match: bool = False,
        category_id: str | None = None,
        supplier_id: str | None = None,
        allowed_document_ids: set[str] | None = None,
        limit: int = 80,
    ) -> list[SearchCandidateRef]:
        lexical_terms = self._flatten_search_terms(query_terms)
        morphology_terms = self._flatten_search_terms(morphology_query_terms or [])
        fuzzy_terms = self._flatten_search_terms(fuzzy_query_terms or [])
        synonym_terms = self._flatten_search_terms(synonym_query_terms or [])
        semantic_texts = self._prepare_semantic_queries(
            semantic_query_texts
            or query_terms
            or fuzzy_query_terms
            or []
        )

        if (
            not lexical_terms
            and not morphology_terms
            and not fuzzy_terms
            and not synonym_terms
            and not semantic_texts
            and structured_query is None
        ):
            return self._fallback_candidate_refs(
                category_id=category_id,
                supplier_id=supplier_id,
            )

        index = self._get_hybrid_index()
        retrieval_results = index.search(
            lexical_terms=lexical_terms,
            morphology_terms=morphology_terms,
            synonym_terms=synonym_terms,
            trigram_terms=fuzzy_terms,
            semantic_texts=semantic_texts,
            structured_query=structured_query,
            strict_match=strict_match,
            category_id=category_id,
            supplier_id=supplier_id,
            allowed_document_ids=allowed_document_ids,
            limit=limit,
        )
        if not retrieval_results:
            return []

        return [
            SearchCandidateRef(
                document_id=result.document_id,
                retrieval_score=result.score,
                retrieval_reasons=result.reasons or ["retrieval_rrf"],
                retrieval_channel_scores=result.channel_scores,
                retrieval_channel_ranks=result.channel_ranks,
                retrieval_features=result.features,
            )
            for result in retrieval_results
        ]

    def _search_candidate_refs_postgres(
        self,
        query_terms: list[str],
        query_text_variants: list[str] | None = None,
        morphology_query_terms: list[str] | None = None,
        fuzzy_query_terms: list[str] | None = None,
        synonym_query_terms: list[str] | None = None,
        semantic_query_texts: list[str] | None = None,
        structured_query: SearchTextAnalysis | None = None,
        strict_match: bool = False,
        category_id: str | None = None,
        supplier_id: str | None = None,
        allowed_document_ids: set[str] | None = None,
        limit: int = 80,
    ) -> list[SearchCandidateRef]:
        lexical_terms = self._flatten_search_terms(query_terms)
        morphology_terms = self._flatten_search_terms(morphology_query_terms or [])
        fuzzy_terms = self._flatten_search_terms(fuzzy_query_terms or [])
        synonym_terms = self._flatten_search_terms(synonym_query_terms or [])

        if (
            not lexical_terms
            and not morphology_terms
            and not fuzzy_terms
            and not synonym_terms
            and structured_query is None
        ):
            return self._fallback_candidate_refs(
                category_id=category_id,
                supplier_id=supplier_id,
            )

        candidate_pool_limit = min(
            RETRIEVAL_MAX_CANDIDATE_POOL,
            max(limit * 8, RETRIEVAL_MIN_CANDIDATE_POOL),
        )
        channel_results = self._build_postgres_channel_results(
            lexical_terms=lexical_terms,
            query_text_variants=query_text_variants or [],
            morphology_terms=morphology_terms,
            synonym_terms=synonym_terms,
            fuzzy_terms=fuzzy_terms,
            structured_query=structured_query,
            category_id=category_id,
            supplier_id=supplier_id,
            allowed_document_ids=allowed_document_ids,
            limit=candidate_pool_limit,
        )
        if settings.ranking_mode.strip().lower() == "retrieval_only" and not strict_match:
            return self._rrf_merge_postgres_refs(channel_results, limit=limit)

        shortlist_ids = self._extract_postgres_shortlist_ids(
            channel_results,
            limit=candidate_pool_limit,
        )
        if not shortlist_ids:
            return []

        shortlist_documents = self._load_search_documents_by_ids(shortlist_ids)
        if not shortlist_documents:
            return []

        shortlist_index = HybridSearchIndex(
            shortlist_documents,
            enable_semantic=False,
            progress=False,
        )
        retrieval_results = shortlist_index.search(
            lexical_terms=lexical_terms,
            morphology_terms=morphology_terms,
            synonym_terms=synonym_terms,
            trigram_terms=fuzzy_terms,
            semantic_texts=[],
            structured_query=structured_query,
            strict_match=strict_match,
            category_id=category_id,
            supplier_id=supplier_id,
            allowed_document_ids=allowed_document_ids,
            limit=limit,
        )
        if not retrieval_results:
            return []

        return [
            SearchCandidateRef(
                document_id=result.document_id,
                retrieval_score=result.score,
                retrieval_reasons=result.reasons or ["retrieval_rrf"],
                retrieval_channel_scores=result.channel_scores,
                retrieval_channel_ranks=result.channel_ranks,
                retrieval_features=result.features,
            )
            for result in retrieval_results
        ]

    def get_synonyms(self, terms: list[str]) -> list[str]:
        return [item.synonym for item in self.get_synonym_expansions(terms)]

    def get_synonym_expansions(self, terms: list[str]) -> list[SynonymExpansion]:
        cleaned_terms = [term.strip() for term in terms if term.strip()]
        if not cleaned_terms:
            return []

        stmt = select(SynonymModel).where(SynonymModel.term.in_(cleaned_terms))
        rows = list(self.session.scalars(stmt))
        expansions: list[SynonymExpansion] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (row.term, row.synonym)
            if key in seen:
                continue
            seen.add(key)
            try:
                weight = float(row.weight)
            except (TypeError, ValueError):
                weight = 1.0
            expansions.append(
                SynonymExpansion(
                    term=row.term,
                    synonym=row.synonym,
                    weight=weight,
                    source=row.source,
                )
            )
        return expansions

    def get_spell_corrections(self, query: str) -> dict[str, str]:
        cleaned_terms = [term.strip() for term in query.split() if term.strip()]
        if not cleaned_terms:
            return {}

        stmt = select(SpellCorrectionModel).where(
            SpellCorrectionModel.wrong_term.in_(cleaned_terms)
        )
        rows = list(self.session.scalars(stmt))
        return {row.wrong_term: row.correct_term for row in rows}

    def get_search_vocabulary(self) -> set[str]:
        cache = self.__class__._search_vocabulary_cache
        if cache is not None:
            return cache

        spell_vocabulary = self.get_search_spell_vocabulary()
        vocabulary = set(spell_vocabulary.tokens)
        self.__class__._search_vocabulary_cache = vocabulary
        return vocabulary

    def get_search_spell_vocabulary(self) -> SpellVocabularyIndex:
        cache = self.__class__._search_spell_vocabulary_cache
        if cache is not None:
            return cache

        if self._get_retrieval_backend() == POSTGRES_RETRIEVAL_BACKEND:
            cache = self._build_lightweight_search_spell_vocabulary()
        else:
            cache = self._build_search_spell_vocabulary(self._get_hybrid_index())
        self.__class__._search_spell_vocabulary_cache = cache
        self.__class__._search_vocabulary_cache = set(cache.tokens)
        return cache

    def _get_hybrid_index(self) -> HybridSearchIndex:
        signature = self._get_catalog_signature()
        cache = self.__class__._hybrid_index_cache
        if cache is not None and self.__class__._hybrid_index_signature == signature:
            return cache

        with self.__class__._hybrid_index_lock:
            cache = self.__class__._hybrid_index_cache
            if cache is not None and self.__class__._hybrid_index_signature == signature:
                return cache

            persisted_cache = self._load_persisted_hybrid_index(signature)
            if persisted_cache is not None:
                self.__class__._hybrid_index_cache = persisted_cache
                self.__class__._hybrid_index_signature = signature
                spell_vocabulary = self._build_search_spell_vocabulary(persisted_cache)
                self.__class__._search_vocabulary_cache = set(spell_vocabulary.tokens)
                self.__class__._search_spell_vocabulary_cache = spell_vocabulary
                return persisted_cache

            documents = self._iter_search_documents()
            cache = HybridSearchIndex(
                documents,
                enable_semantic=settings.search_semantic_backend.strip().lower() != "disabled",
                progress=True,
            )
            self.__class__._hybrid_index_cache = cache
            self.__class__._hybrid_index_signature = signature
            spell_vocabulary = self._build_search_spell_vocabulary(cache)
            self.__class__._search_vocabulary_cache = set(spell_vocabulary.tokens)
            self.__class__._search_spell_vocabulary_cache = spell_vocabulary
            self._save_persisted_hybrid_index(signature, cache)
            return cache

    def _iter_search_documents(self) -> Iterator[SearchDocument]:
        stmt = (
            select(
                STEItemModel.id.label("item_id"),
                STEItemModel.title.label("title"),
                STEItemModel.description.label("description"),
                STEItemModel.category_id.label("category_id"),
                CategoryModel.name.label("category_name"),
                STEItemModel.supplier_id.label("supplier_id"),
                SupplierModel.name.label("supplier_name"),
                STEItemModel.attributes_json.label("attributes_json"),
                STEItemModel.status.label("status"),
                STEItemModel.updated_at.label("updated_at"),
            )
            .join(CategoryModel, STEItemModel.category_id == CategoryModel.id)
            .join(SupplierModel, STEItemModel.supplier_id == SupplierModel.id)
            .order_by(STEItemModel.updated_at.desc(), STEItemModel.title.asc())
            .execution_options(yield_per=500)
        )
        for row in self.session.execute(stmt).mappings():
            attributes = row["attributes_json"]
            if not isinstance(attributes, dict):
                attributes = {}

            yield SearchDocument(
                id=str(row["item_id"]),
                title=str(row["title"] or ""),
                description=str(row["description"] or ""),
                category_id=str(row["category_id"] or ""),
                category_name=str(row["category_name"] or ""),
                supplier_id=str(row["supplier_id"] or ""),
                supplier_name=str(row["supplier_name"] or ""),
                attributes={str(key): str(value) for key, value in attributes.items()},
                status=str(row["status"] or "active"),
                updated_at=row["updated_at"],
            )

    def load_search_item_snapshots(
        self,
        item_ids: list[str],
    ) -> dict[str, SearchItemSnapshot]:
        if not item_ids:
            return {}

        stmt = (
            select(
                STEItemModel.id.label("item_id"),
                STEItemModel.title.label("title"),
                STEItemModel.description.label("description"),
                STEItemModel.category_id.label("category_id"),
                CategoryModel.name.label("category_name"),
                STEItemModel.supplier_id.label("supplier_id"),
                SupplierModel.name.label("supplier_name"),
                STEItemModel.attributes_json.label("attributes_json"),
                STEItemModel.status.label("status"),
            )
            .join(CategoryModel, STEItemModel.category_id == CategoryModel.id)
            .join(SupplierModel, STEItemModel.supplier_id == SupplierModel.id)
            .where(STEItemModel.id.in_(item_ids))
        )
        return {
            snapshot.id: snapshot
            for snapshot in (
                self._build_search_item_snapshot(row)
                for row in self.session.execute(stmt).mappings()
            )
        }

    def _load_search_documents_by_ids(
        self,
        item_ids: list[str],
    ) -> list[SearchDocument]:
        if not item_ids:
            return []

        stmt = (
            select(
                STEItemModel.id.label("item_id"),
                STEItemModel.title.label("title"),
                STEItemModel.description.label("description"),
                STEItemModel.category_id.label("category_id"),
                CategoryModel.name.label("category_name"),
                STEItemModel.supplier_id.label("supplier_id"),
                SupplierModel.name.label("supplier_name"),
                STEItemModel.attributes_json.label("attributes_json"),
                STEItemModel.status.label("status"),
                STEItemModel.updated_at.label("updated_at"),
            )
            .join(CategoryModel, STEItemModel.category_id == CategoryModel.id)
            .join(SupplierModel, STEItemModel.supplier_id == SupplierModel.id)
            .where(STEItemModel.id.in_(item_ids))
        )
        documents_by_id: dict[str, SearchDocument] = {}
        for row in self.session.execute(stmt).mappings():
            attributes = row["attributes_json"]
            if not isinstance(attributes, dict):
                attributes = {}

            document = SearchDocument(
                id=str(row["item_id"]),
                title=str(row["title"] or ""),
                description=str(row["description"] or ""),
                category_id=str(row["category_id"] or ""),
                category_name=str(row["category_name"] or ""),
                supplier_id=str(row["supplier_id"] or ""),
                supplier_name=str(row["supplier_name"] or ""),
                attributes={str(key): str(value) for key, value in attributes.items()},
                status=str(row["status"] or "active"),
                updated_at=row["updated_at"],
            )
            documents_by_id[document.id] = document

        return [
            documents_by_id[item_id]
            for item_id in item_ids
            if item_id in documents_by_id
        ]

    def _build_search_vocabulary(self, index: HybridSearchIndex) -> set[str]:
        return set(self._build_search_spell_vocabulary(index).tokens)

    def _build_search_spell_vocabulary(
        self,
        index: HybridSearchIndex,
    ) -> SpellVocabularyIndex:
        vocabulary: set[str] = set()
        token_document_frequencies: Counter[str] = Counter()
        protected_tokens: set[str] = set()
        min_document_frequency = 1 if len(index.documents) < 25 else 2

        for row in self.session.execute(
            select(SpellCorrectionModel.wrong_term, SpellCorrectionModel.correct_term)
        ):
            vocabulary.update(self._extract_tokens(row.wrong_term))
            vocabulary.update(self._extract_tokens(row.correct_term))

        for row in self.session.execute(select(SynonymModel.term, SynonymModel.synonym)):
            vocabulary.update(self._extract_tokens(row.term))
            vocabulary.update(self._extract_tokens(row.synonym))

        for document in index.documents:
            useful_document_tokens: set[str] = set()
            for field_name in ("title", "category", "attributes"):
                useful_document_tokens.update(document.field_term_sets[field_name])

            token_document_frequencies.update(
                token
                for token in useful_document_tokens
                if len(token) >= 3 and not token.isdigit()
            )
            protected_tokens.update(document.combined_analysis.brand_terms)
            protected_tokens.update(document.combined_analysis.model_terms)
            protected_tokens.update(document.combined_analysis.code_terms)
            protected_tokens.update(document.combined_analysis.size_terms)

        vocabulary.update(
            token
            for token, frequency in token_document_frequencies.items()
            if frequency >= min_document_frequency
        )

        return build_spell_vocabulary_index(
            vocabulary,
            token_frequencies=token_document_frequencies,
            protected_tokens=protected_tokens,
        )

    def _build_lightweight_search_spell_vocabulary(self) -> SpellVocabularyIndex:
        vocabulary: set[str] = set()
        token_document_frequencies: Counter[str] = Counter()
        min_document_frequency = 1

        for row in self.session.execute(
            select(SpellCorrectionModel.wrong_term, SpellCorrectionModel.correct_term)
        ):
            vocabulary.update(self._extract_tokens(row.wrong_term))
            vocabulary.update(self._extract_tokens(row.correct_term))

        for row in self.session.execute(select(SynonymModel.term, SynonymModel.synonym)):
            vocabulary.update(self._extract_tokens(row.term))
            vocabulary.update(self._extract_tokens(row.synonym))

        stmt = (
            select(
                STEItemModel.title.label("title"),
                CategoryModel.name.label("category_name"),
                STEItemModel.attributes_json.label("attributes_json"),
            )
            .join(CategoryModel, STEItemModel.category_id == CategoryModel.id)
            .execution_options(yield_per=1000)
        )
        document_count = 0
        for row in self.session.execute(stmt).mappings():
            document_count += 1
            attributes = row["attributes_json"]
            if not isinstance(attributes, dict):
                attributes = {}

            attributes_text = " ".join(
                f"{key} {value}".strip()
                for key, value in attributes.items()
                if key or value
            )
            useful_document_tokens = set()
            useful_document_tokens.update(extract_query_terms(str(row["title"] or "")))
            useful_document_tokens.update(extract_query_terms(str(row["category_name"] or "")))
            useful_document_tokens.update(extract_query_terms(attributes_text))
            token_document_frequencies.update(
                token
                for token in useful_document_tokens
                if len(token) >= 3 and not token.isdigit()
            )

        if document_count >= 25:
            min_document_frequency = 2

        vocabulary.update(
            token
            for token, frequency in token_document_frequencies.items()
            if frequency >= min_document_frequency
        )

        return build_spell_vocabulary_index(
            vocabulary,
            token_frequencies=token_document_frequencies,
        )

    def _build_postgres_channel_results(
        self,
        *,
        lexical_terms: list[str],
        query_text_variants: list[str],
        morphology_terms: list[str],
        synonym_terms: list[str],
        fuzzy_terms: list[str],
        structured_query: SearchTextAnalysis | None,
        category_id: str | None,
        supplier_id: str | None,
        allowed_document_ids: set[str] | None,
        limit: int,
    ) -> dict[str, list[dict[str, Any]]]:
        if allowed_document_ids is not None:
            allowed_rows = [
                {
                    "document_id": document_id,
                    "score": 1.0,
                    "updated_at": datetime.min,
                }
                for document_id in list(allowed_document_ids)[:limit]
            ]
            return {"bm25": allowed_rows}

        primary_query = structured_query.normalized_text if structured_query else ""
        lexical_query_variants = self._deduplicate_non_empty(
            [
                primary_query,
                *query_text_variants,
            ]
        )[:4]
        lexical_query = normalize_query(" ".join(lexical_terms))
        morphology_query = normalize_query(" ".join(morphology_terms))
        synonym_query = normalize_query(" ".join(synonym_terms))
        trigram_queries = self._deduplicate_non_empty(
            [
                primary_query,
                *query_text_variants,
                *fuzzy_terms,
            ]
        )[:6]

        channel_results: dict[str, list[dict[str, Any]]] = {}
        if lexical_query and lexical_query not in lexical_query_variants:
            lexical_query_variants.append(lexical_query)
        if lexical_query_variants:
            bm25_rows: list[dict[str, Any]] = []
            for query_text in lexical_query_variants:
                rows = self._run_postgres_fts_query(
                    query_text=query_text,
                    category_id=category_id,
                    supplier_id=supplier_id,
                    limit=limit,
                )
                if rows:
                    bm25_rows.extend(rows)
            if bm25_rows:
                channel_results["bm25"] = self._merge_ranked_rows_by_document(
                    bm25_rows,
                    limit=limit,
                )

        if morphology_query and morphology_query not in {*lexical_query_variants}:
            channel_results["morphology"] = self._run_postgres_fts_query(
                query_text=morphology_query,
                category_id=category_id,
                supplier_id=supplier_id,
                limit=limit,
            )

        if synonym_query and synonym_query not in {*lexical_query_variants, morphology_query}:
            channel_results["synonym_bm25"] = self._run_postgres_fts_query(
                query_text=synonym_query,
                category_id=category_id,
                supplier_id=supplier_id,
                limit=limit,
            )

        if self._should_run_postgres_trigram_fallback(channel_results, limit=limit):
            fuzzy_rows: list[dict[str, Any]] = []
            for query_text in trigram_queries:
                rows = self._run_postgres_trigram_query(
                    query_text=query_text,
                    category_id=category_id,
                    supplier_id=supplier_id,
                    limit=limit,
                )
                if rows:
                    fuzzy_rows.extend(rows)
            if fuzzy_rows:
                channel_results["fuzzy"] = self._merge_ranked_rows_by_document(
                    fuzzy_rows,
                    limit=limit,
                )

        return channel_results

    @staticmethod
    def _should_run_postgres_trigram_fallback(
        channel_results: dict[str, list[dict[str, Any]]],
        *,
        limit: int,
    ) -> bool:
        if not channel_results:
            return True

        unique_ids = {
            str(row["document_id"])
            for rows in channel_results.values()
            for row in rows
        }
        threshold = max(min(limit, 20), 8)
        return len(unique_ids) < threshold

    def _extract_postgres_shortlist_ids(
        self,
        channel_results: dict[str, list[dict[str, Any]]],
        *,
        limit: int,
    ) -> list[str]:
        return [
            ref.document_id
            for ref in self._rrf_merge_postgres_refs(channel_results, limit=limit)
        ]

    def _run_postgres_fts_query(
        self,
        *,
        query_text: str,
        category_id: str | None,
        supplier_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        normalized_query = normalize_query(query_text)
        if not normalized_query:
            return []

        sql = (
            "SELECT ste.id AS document_id, "
            f"ts_rank_cd({POSTGRES_SEARCH_VECTOR_SQL}, websearch_to_tsquery('simple', :query_text)) AS score, "
            "ste.updated_at AS updated_at "
            "FROM ste_items ste "
            f"WHERE {POSTGRES_SEARCH_VECTOR_SQL} @@ websearch_to_tsquery('simple', :query_text) "
        )
        params: dict[str, Any] = {
            "query_text": normalized_query,
            "limit": limit,
        }
        if category_id:
            sql += "AND ste.category_id = :category_id "
            params["category_id"] = category_id
        if supplier_id:
            sql += "AND ste.supplier_id = :supplier_id "
            params["supplier_id"] = supplier_id
        sql += (
            "ORDER BY score DESC, ste.updated_at DESC, ste.title ASC "
            "LIMIT :limit"
        )

        rows = self.session.execute(text(sql), params).mappings()
        results: list[dict[str, Any]] = []
        for row in rows:
            score = float(row["score"] or 0.0)
            if score < POSTGRES_FTS_MIN_SCORE:
                continue
            results.append(
                {
                    "document_id": str(row["document_id"]),
                    "score": score,
                    "updated_at": row["updated_at"],
                }
            )
        return results

    def _run_postgres_trigram_query(
        self,
        *,
        query_text: str,
        category_id: str | None,
        supplier_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        normalized_query = normalize_query(query_text)
        if len(normalized_query) < 3:
            return []

        sql = (
            "SELECT ste.id AS document_id, "
            f"{POSTGRES_TRGM_SCORE_SQL} AS score, "
            "ste.updated_at AS updated_at "
            "FROM ste_items ste "
            "WHERE ("
            "ste.title % :query_text "
            ") "
        )
        params: dict[str, Any] = {
            "query_text": normalized_query,
            "limit": limit,
        }
        if category_id:
            sql += "AND ste.category_id = :category_id "
            params["category_id"] = category_id
        if supplier_id:
            sql += "AND ste.supplier_id = :supplier_id "
            params["supplier_id"] = supplier_id
        sql += (
            "ORDER BY score DESC, ste.updated_at DESC, ste.title ASC "
            "LIMIT :limit"
        )

        rows = self.session.execute(text(sql), params).mappings()
        results: list[dict[str, Any]] = []
        for row in rows:
            score = float(row["score"] or 0.0)
            if score < POSTGRES_TRGM_MIN_SCORE:
                continue
            results.append(
                {
                    "document_id": str(row["document_id"]),
                    "score": score,
                    "updated_at": row["updated_at"],
                }
            )
        return results

    @staticmethod
    def _merge_ranked_rows_by_document(
        rows: list[dict[str, Any]],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        best_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            document_id = str(row["document_id"])
            current = best_by_id.get(document_id)
            if current is None or float(row["score"]) > float(current["score"]):
                best_by_id[document_id] = row

        merged = sorted(
            best_by_id.values(),
            key=lambda row: (
                float(row["score"]),
                row["updated_at"] or datetime.min,
            ),
            reverse=True,
        )
        return merged[:limit]

    def _rrf_merge_postgres_refs(
        self,
        channel_results: dict[str, list[dict[str, Any]]],
        *,
        limit: int,
    ) -> list[SearchCandidateRef]:
        if not channel_results:
            return []

        k = 60
        fused_scores: dict[str, float] = {}
        best_scores: dict[str, float] = {}
        updated_at_by_id: dict[str, datetime | None] = {}
        channel_scores_by_id: dict[str, dict[str, float]] = {}
        channel_ranks_by_id: dict[str, dict[str, int]] = {}
        feature_map_by_id: dict[str, dict[str, float]] = {}

        for channel_name, ranking in channel_results.items():
            if not ranking:
                continue
            channel_weight = CHANNEL_RRF_WEIGHTS.get(channel_name, 1.0)
            for rank, row in enumerate(ranking, start=1):
                document_id = str(row["document_id"])
                fused_scores[document_id] = fused_scores.get(document_id, 0.0) + (
                    channel_weight / (k + rank)
                )
                best_scores[document_id] = max(
                    best_scores.get(document_id, 0.0),
                    float(row["score"]),
                )
                updated_at_by_id[document_id] = row.get("updated_at")
                channel_scores_by_id.setdefault(document_id, {})[channel_name] = round(
                    float(row["score"]),
                    4,
                )
                channel_ranks_by_id.setdefault(document_id, {})[channel_name] = rank
                feature_map_by_id.setdefault(document_id, {})[
                    f"channel_hit_{channel_name}"
                ] = 1.0

        ranked_ids = sorted(
            fused_scores,
            key=lambda document_id: (
                fused_scores[document_id],
                best_scores.get(document_id, 0.0),
                updated_at_by_id.get(document_id) or datetime.min,
            ),
            reverse=True,
        )
        max_rrf_score = sum(CHANNEL_RRF_WEIGHTS.values()) / (k + 1)
        refs: list[SearchCandidateRef] = []
        for document_id in ranked_ids[:limit]:
            channel_scores = channel_scores_by_id.get(document_id, {})
            feature_map = feature_map_by_id.setdefault(document_id, {})
            feature_map["retrieval_channel_count"] = float(len(channel_scores))
            feature_map["appeared_in_multiple_channels"] = float(len(channel_scores) >= 2)
            reasons = [
                CHANNEL_REASON_MAP[channel_name]
                for channel_name in channel_scores
                if channel_name in CHANNEL_REASON_MAP
            ]
            if len(channel_scores) >= 2:
                reasons.append("retrieval_rrf")
            refs.append(
                SearchCandidateRef(
                    document_id=document_id,
                    retrieval_score=round(
                        min(fused_scores[document_id] / max(max_rrf_score, 1e-6), 1.0),
                        4,
                    ),
                    retrieval_reasons=list(dict.fromkeys(reasons or ["retrieval_rrf"])),
                    retrieval_channel_scores=channel_scores,
                    retrieval_channel_ranks=channel_ranks_by_id.get(document_id, {}),
                    retrieval_features=feature_map,
                )
            )
        return refs

    @staticmethod
    def _deduplicate_non_empty(values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = normalize_query(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @classmethod
    def _resolve_search_index_cache_path(cls) -> Path | None:
        raw_path = settings.search_index_cache_path.strip()
        if not raw_path:
            return None
        return Path(raw_path).expanduser()

    @classmethod
    def _load_persisted_hybrid_index(
        cls,
        signature: tuple[int, datetime | None],
    ) -> HybridSearchIndex | None:
        cache_path = cls._resolve_search_index_cache_path()
        if cache_path is None or not cache_path.exists():
            return None

        try:
            with cache_path.open("rb") as handle:
                payload = pickle.load(handle)
        except Exception as exc:
            LOGGER.warning("Failed to read persisted search index cache %s: %s", cache_path, exc)
            cache_path.unlink(missing_ok=True)
            return None

        if not isinstance(payload, dict):
            cache_path.unlink(missing_ok=True)
            return None

        if payload.get("version") != cls._INDEX_CACHE_FORMAT_VERSION:
            return None
        if payload.get("signature") != signature:
            return None
        if payload.get("requested_semantic_backend") != settings.search_semantic_backend.strip().lower():
            return None

        index = payload.get("index")
        if not isinstance(index, HybridSearchIndex):
            cache_path.unlink(missing_ok=True)
            return None

        LOGGER.info("Loaded persisted search index cache from %s", cache_path)
        return index

    @classmethod
    def _save_persisted_hybrid_index(
        cls,
        signature: tuple[int, datetime | None],
        index: HybridSearchIndex,
    ) -> None:
        cache_path = cls._resolve_search_index_cache_path()
        if cache_path is None:
            return

        payload = {
            "version": cls._INDEX_CACHE_FORMAT_VERSION,
            "signature": signature,
            "requested_semantic_backend": settings.search_semantic_backend.strip().lower(),
            "index": index,
        }

        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with cache_path.open("wb") as handle:
                pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:
            LOGGER.warning("Failed to persist search index cache %s: %s", cache_path, exc)
            return

        LOGGER.info("Persisted search index cache to %s", cache_path)

    def _get_catalog_signature(self) -> tuple[int, datetime | None]:
        stmt = select(
            func.count(STEItemModel.id),
            func.max(STEItemModel.updated_at),
        )
        row = self.session.execute(stmt).one()
        return int(row[0] or 0), row[1]

    def _fallback_candidate_refs(
        self,
        *,
        category_id: str | None,
        supplier_id: str | None,
    ) -> list[SearchCandidateRef]:
        stmt = (
            select(STEItemModel.id)
            .order_by(STEItemModel.updated_at.desc(), STEItemModel.title.asc())
            .limit(50)
        )
        if category_id:
            stmt = stmt.where(STEItemModel.category_id == category_id)
        if supplier_id:
            stmt = stmt.where(STEItemModel.supplier_id == supplier_id)

        return [
            SearchCandidateRef(document_id=str(item_id))
            for item_id in self.session.scalars(stmt)
        ]

    @staticmethod
    def _flatten_search_terms(values: list[str]) -> list[str]:
        tokens: list[str] = []
        for value in values:
            normalized = normalize_query(value)
            if not normalized:
                continue
            tokens.extend(extract_query_terms(normalized))
        return list(dict.fromkeys(token for token in tokens if token))

    @staticmethod
    def _prepare_semantic_queries(values: list[str]) -> list[str]:
        return []

    @classmethod
    def _extract_tokens(cls, value: str | None) -> set[str]:
        if not value:
            return set()
        return {
            token.lower()
            for token in cls._search_vocabulary_pattern.findall(value)
            if len(token) >= 3 and not token.isdigit()
        }

    @staticmethod
    def _build_search_item_snapshot(row: dict) -> SearchItemSnapshot:
        attributes = row["attributes_json"]
        if not isinstance(attributes, dict):
            attributes = {}

        attribute_values = [
            str(value).strip()
            for value in attributes.values()
            if str(value).strip()
        ]

        return SearchItemSnapshot(
            id=str(row["item_id"]),
            title=str(row["title"] or ""),
            description=str(row["description"] or ""),
            category_id=str(row["category_id"] or ""),
            category_name=str(row["category_name"] or ""),
            supplier_id=str(row["supplier_id"] or ""),
            supplier_name=str(row["supplier_name"] or ""),
            attributes=attributes,
            attributes_text=" ".join(attribute_values),
            attribute_value_count=len(attributes),
            status=str(row["status"] or "active"),
        )
