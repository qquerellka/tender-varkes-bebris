import logging
import pickle
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.db.models import (
    CategoryModel,
    STEItemModel,
    SearchSessionModel,
    SpellCorrectionModel,
    SupplierModel,
    SynonymModel,
)
from app.domain.search.normalizer import (
    SpellVocabularyIndex,
    build_spell_vocabulary_index,
    extract_query_terms,
    normalize_query,
)
from app.domain.search.query_analysis import SearchTextAnalysis
from app.domain.search.retrieval import HybridSearchIndex, SearchDocument

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SearchCandidateHit:
    item: STEItemModel
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
    _INDEX_CACHE_FORMAT_VERSION = 1
    _hybrid_index_lock = threading.Lock()
    _search_vocabulary_cache: set[str] | None = None
    _search_spell_vocabulary_cache: SpellVocabularyIndex | None = None
    _search_vocabulary_pattern = re.compile(r"[0-9a-zа-яё]+", flags=re.IGNORECASE)
    _hybrid_index_cache: HybridSearchIndex | None = None
    _hybrid_index_signature: tuple[int, datetime | None] | None = None

    def __init__(self, session: Session) -> None:
        self.session = session

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

    def search_candidates(
        self,
        query_terms: list[str],
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
    ) -> list[SearchCandidateHit]:
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
            return self._fallback_candidates(category_id=category_id, supplier_id=supplier_id)

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

        ordered_ids = [result.document_id for result in retrieval_results]
        items_by_id = self._load_items_by_ids(ordered_ids)

        hits: list[SearchCandidateHit] = []
        for result in retrieval_results:
            item = items_by_id.get(result.document_id)
            if item is None:
                continue
            hits.append(
                SearchCandidateHit(
                    item=item,
                    retrieval_score=result.score,
                    retrieval_reasons=result.reasons or ["retrieval_rrf"],
                    retrieval_channel_scores=result.channel_scores,
                    retrieval_channel_ranks=result.channel_ranks,
                    retrieval_features=result.features,
                )
            )
        return hits

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

            documents = self._build_search_documents()
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

    def _build_search_documents(self) -> list[SearchDocument]:
        stmt = (
            select(STEItemModel)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(STEItemModel.updated_at.desc(), STEItemModel.title.asc())
        )
        return [
            SearchDocument(
                id=item.id,
                title=item.title,
                description=item.description,
                category_id=item.category_id,
                category_name=item.category.name if item.category else "",
                supplier_id=item.supplier_id,
                supplier_name=item.supplier.name if item.supplier else "",
                attributes=item.attributes_json,
                status=item.status,
                updated_at=item.updated_at,
            )
            for item in self.session.scalars(stmt)
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
        if index._semantic_faiss_index is not None:
            LOGGER.info(
                "Skipping persisted search index cache because FAISS semantic index is enabled"
            )
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

    def _fallback_candidates(
        self,
        *,
        category_id: str | None,
        supplier_id: str | None,
    ) -> list[SearchCandidateHit]:
        stmt = (
            select(STEItemModel)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(STEItemModel.updated_at.desc(), STEItemModel.title.asc())
            .limit(50)
        )
        if category_id:
            stmt = stmt.where(STEItemModel.category_id == category_id)
        if supplier_id:
            stmt = stmt.where(STEItemModel.supplier_id == supplier_id)

        return [SearchCandidateHit(item=item) for item in self.session.scalars(stmt)]

    def _load_items_by_ids(self, item_ids: list[str]) -> dict[str, STEItemModel]:
        if not item_ids:
            return {}

        stmt = (
            select(STEItemModel)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .where(STEItemModel.id.in_(item_ids))
        )
        return {item.id: item for item in self.session.scalars(stmt)}

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
        prepared: list[str] = []
        for value in values:
            normalized = normalize_query(value)
            if normalized:
                prepared.append(normalized)
        return list(dict.fromkeys(prepared))

    @classmethod
    def _extract_tokens(cls, value: str | None) -> set[str]:
        if not value:
            return set()
        return {
            token.lower()
            for token in cls._search_vocabulary_pattern.findall(value)
            if len(token) >= 3 and not token.isdigit()
        }
