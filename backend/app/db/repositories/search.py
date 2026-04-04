import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm import Session, joinedload

from app.db.models import (
    CategoryModel,
    STEItemModel,
    SearchSessionModel,
    SpellCorrectionModel,
    SupplierModel,
    SynonymModel,
)
from app.domain.search.normalizer import extract_query_terms, normalize_query
from app.domain.search.query_analysis import SearchTextAnalysis
from app.domain.search.retrieval import HybridSearchIndex, SearchDocument


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
    _search_vocabulary_cache: set[str] | None = None
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
            limit=80,
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

        vocabulary: set[str] = set()

        for row in self.session.execute(
            select(SpellCorrectionModel.wrong_term, SpellCorrectionModel.correct_term)
        ):
            vocabulary.update(self._extract_tokens(row.wrong_term))
            vocabulary.update(self._extract_tokens(row.correct_term))

        for row in self.session.execute(select(SynonymModel.term, SynonymModel.synonym)):
            vocabulary.update(self._extract_tokens(row.term))
            vocabulary.update(self._extract_tokens(row.synonym))

        for document in self._get_hybrid_index().documents:
            vocabulary.update(self._extract_tokens(document.payload.title))
            vocabulary.update(self._extract_tokens(document.payload.description))
            vocabulary.update(self._extract_tokens(" ".join(document.payload.attributes.values())))
            vocabulary.update(self._extract_tokens(document.payload.category_name))
            vocabulary.update(self._extract_tokens(document.payload.supplier_name))

        self.__class__._search_vocabulary_cache = vocabulary
        return vocabulary

    def _get_hybrid_index(self) -> HybridSearchIndex:
        signature = self._get_catalog_signature()
        cache = self.__class__._hybrid_index_cache
        if cache is not None and self.__class__._hybrid_index_signature == signature:
            return cache

        stmt = (
            select(STEItemModel)
            .options(joinedload(STEItemModel.category), joinedload(STEItemModel.supplier))
            .order_by(STEItemModel.updated_at.desc(), STEItemModel.title.asc())
        )
        documents = [
            SearchDocument(
                id=item.id,
                title=item.title,
                description=item.description,
                category_id=item.category_id,
                category_name=item.category.name,
                supplier_id=item.supplier_id,
                supplier_name=item.supplier.name,
                attributes=item.attributes_json,
                status=item.status,
                updated_at=item.updated_at,
            )
            for item in self.session.scalars(stmt)
        ]

        cache = HybridSearchIndex(documents)
        self.__class__._hybrid_index_cache = cache
        self.__class__._hybrid_index_signature = signature
        self.__class__._search_vocabulary_cache = None
        return cache

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
