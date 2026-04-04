from __future__ import annotations

import json
import importlib
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _install_backend_settings_stub() -> None:
    try:
        import pydantic_settings  # noqa: F401
        return
    except ImportError:
        pass

    if "app.core.config" in sys.modules:
        return

    stub_core_module = sys.modules.get("app.core")
    if stub_core_module is None:
        stub_core_module = types.ModuleType("app.core")
        sys.modules["app.core"] = stub_core_module

    stub_config_module = types.ModuleType("app.core.config")

    class _StubSettings:
        search_semantic_backend = "auto"
        search_semantic_model_name = "BAAI/bge-m3"
        search_semantic_batch_size = 12
        search_semantic_max_length = 2048
        search_semantic_use_fp16 = False
        search_semantic_use_faiss = True
        search_semantic_candidate_pool = 240
        search_semantic_dense_min_score = 0.2
        search_semantic_fallback_min_score = 0.12

    stub_config_module.settings = _StubSettings()
    sys.modules["app.core.config"] = stub_config_module
    setattr(stub_core_module, "config", stub_config_module)
    try:
        app_module = importlib.import_module("app")
        setattr(app_module, "core", stub_core_module)
    except Exception:
        pass


_install_backend_settings_stub()

from app.domain.search.normalizer import (
    correct_keyboard_layout,
    correct_query,
    correct_query_fuzzy,
    expand_fuzzy_term_variants,
    expand_term_variants,
    extract_query_terms,
    lemmatize_query_terms,
    normalize_query,
)
from app.domain.search.query_analysis import SearchTextAnalysis, analyze_search_text
from app.domain.search.retrieval import HybridSearchIndex, RetrievalResult, SearchDocument

VOCAB_TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", flags=re.IGNORECASE)
CHANNEL_NAMES = (
    "exact_structured",
    "attribute",
    "bm25",
    "morphology",
    "fuzzy",
    "synonym_bm25",
    "semantic",
)
RETRIEVAL_REASON_COLUMNS = {
    "retrieval_exact": "retrieval_exact",
    "retrieval_attribute": "retrieval_attribute",
    "retrieval_bm25": "retrieval_bm25",
    "retrieval_morphology": "retrieval_morphology",
    "retrieval_fuzzy": "retrieval_fuzzy",
    "retrieval_synonym": "retrieval_synonym",
    "retrieval_semantic": "retrieval_semantic",
    "retrieval_rrf": "retrieval_rrf",
}
RETRIEVAL_FEATURE_COLUMNS = (
    "exact_match_flag",
    "phrase_match_flag",
    "category_match_flag",
    "brand_match_flag",
    "numeric_constraint_match_flag",
    "attribute_overlap_count",
    "appeared_in_multiple_channels",
    "strict_term_coverage",
    "fuzzy_edit_score",
    "semantic_backend_bge_m3",
    "semantic_backend_fallback",
    "semantic_via_faiss",
)


@dataclass(frozen=True, slots=True)
class SynonymExpansionRecord:
    term: str
    synonym: str
    weight: float
    source: str


@dataclass(slots=True)
class PreparedQuery:
    normalized_query: str
    corrected_query: str | None
    applied_synonyms: list[str]
    lexical_terms: list[str]
    morphology_terms: list[str]
    fuzzy_terms: list[str]
    synonym_terms: list[str]
    semantic_texts: list[str]
    structured_query: SearchTextAnalysis


@dataclass(slots=True)
class SessionRetrievalFeatures:
    normalized_query: str
    corrected_query: str | None
    applied_synonyms: list[str]
    query_has_correction: float
    query_has_synonyms: float
    features_by_item_id: dict[str, dict[str, float]]


class RetrievalFeatureBuilder:
    def __init__(
        self,
        *,
        item_by_id: dict[str, dict[str, str]],
        category_by_id: dict[str, dict[str, str]],
        supplier_by_id: dict[str, dict[str, str]],
        synonym_rows: list[dict[str, str]],
        spell_rows: list[dict[str, str]],
    ) -> None:
        self.documents = self._build_documents(
            item_by_id=item_by_id,
            category_by_id=category_by_id,
            supplier_by_id=supplier_by_id,
        )
        self.index = HybridSearchIndex(self.documents)
        self.synonym_map = self._build_synonym_map(synonym_rows)
        self.spell_corrections = self._build_spell_corrections(spell_rows)
        self.search_vocabulary = self._build_search_vocabulary(
            documents=self.documents,
            synonym_map=self.synonym_map,
            spell_corrections=self.spell_corrections,
        )
        self._query_cache: dict[tuple[str, str], SessionRetrievalFeatures] = {}

    def build_session_feature_map(
        self,
        session_queries: dict[str, tuple[str, str]],
    ) -> dict[str, SessionRetrievalFeatures]:
        session_features: dict[str, SessionRetrievalFeatures] = {}
        for session_id, (query, normalized_query) in session_queries.items():
            cache_key = (query, normalized_query)
            cached = self._query_cache.get(cache_key)
            if cached is None:
                cached = self._build_query_features(query=query, normalized_query=normalized_query)
                self._query_cache[cache_key] = cached
            session_features[session_id] = cached
        return session_features

    @staticmethod
    def _build_documents(
        *,
        item_by_id: dict[str, dict[str, str]],
        category_by_id: dict[str, dict[str, str]],
        supplier_by_id: dict[str, dict[str, str]],
    ) -> list[SearchDocument]:
        documents: list[SearchDocument] = []
        for item in item_by_id.values():
            category = category_by_id.get(item.get("category_id", ""), {})
            supplier = supplier_by_id.get(item.get("supplier_id", ""), {})
            attributes = _safe_json(item.get("attributes_json"), default={})
            if not isinstance(attributes, dict):
                attributes = {}
            documents.append(
                SearchDocument(
                    id=item.get("id", ""),
                    title=item.get("title", ""),
                    description=item.get("description", ""),
                    category_id=item.get("category_id", ""),
                    category_name=category.get("name", ""),
                    supplier_id=item.get("supplier_id", ""),
                    supplier_name=supplier.get("name", ""),
                    attributes={str(key): str(value) for key, value in attributes.items()},
                    status=item.get("status", "active"),
                )
            )
        return documents

    @staticmethod
    def _build_synonym_map(
        rows: list[dict[str, str]],
    ) -> dict[str, list[SynonymExpansionRecord]]:
        synonym_map: dict[str, list[SynonymExpansionRecord]] = {}
        for row in rows:
            term = normalize_query(str(row.get("term", "")))
            synonym = normalize_query(str(row.get("synonym", "")))
            if not term or not synonym:
                continue
            try:
                weight = float(row.get("weight") or 1.0)
            except (TypeError, ValueError):
                weight = 1.0
            synonym_map.setdefault(term, []).append(
                SynonymExpansionRecord(
                    term=term,
                    synonym=synonym,
                    weight=weight,
                    source=str(row.get("source") or ""),
                )
            )
        return synonym_map

    @staticmethod
    def _build_spell_corrections(rows: list[dict[str, str]]) -> dict[str, str]:
        corrections: dict[str, str] = {}
        for row in rows:
            wrong_term = normalize_query(str(row.get("wrong_term", "")))
            correct_term = normalize_query(str(row.get("correct_term", "")))
            if wrong_term and correct_term:
                corrections[wrong_term] = correct_term
        return corrections

    @staticmethod
    def _build_search_vocabulary(
        *,
        documents: list[SearchDocument],
        synonym_map: dict[str, list[SynonymExpansionRecord]],
        spell_corrections: dict[str, str],
    ) -> set[str]:
        vocabulary: set[str] = set()

        for wrong_term, correct_term in spell_corrections.items():
            vocabulary.update(_extract_vocab_tokens(wrong_term))
            vocabulary.update(_extract_vocab_tokens(correct_term))

        for term, expansions in synonym_map.items():
            vocabulary.update(_extract_vocab_tokens(term))
            for expansion in expansions:
                vocabulary.update(_extract_vocab_tokens(expansion.synonym))

        for document in documents:
            vocabulary.update(_extract_vocab_tokens(document.title))
            vocabulary.update(_extract_vocab_tokens(document.description))
            vocabulary.update(_extract_vocab_tokens(document.category_name))
            vocabulary.update(_extract_vocab_tokens(document.supplier_name))
            vocabulary.update(_extract_vocab_tokens(" ".join(document.attributes.values())))

        return vocabulary

    def _build_query_features(
        self,
        *,
        query: str,
        normalized_query: str,
    ) -> SessionRetrievalFeatures:
        prepared_query = self._prepare_query(query=query, normalized_query=normalized_query)
        if not (
            prepared_query.lexical_terms
            or prepared_query.morphology_terms
            or prepared_query.fuzzy_terms
            or prepared_query.synonym_terms
            or prepared_query.semantic_texts
            or prepared_query.structured_query.normalized_text
        ):
            return SessionRetrievalFeatures(
                normalized_query=prepared_query.normalized_query,
                corrected_query=prepared_query.corrected_query,
                applied_synonyms=prepared_query.applied_synonyms,
                query_has_correction=float(bool(prepared_query.corrected_query)),
                query_has_synonyms=float(bool(prepared_query.applied_synonyms)),
                features_by_item_id={},
            )

        retrieval_results = self.index.search(
            lexical_terms=prepared_query.lexical_terms,
            morphology_terms=prepared_query.morphology_terms,
            synonym_terms=prepared_query.synonym_terms,
            trigram_terms=prepared_query.fuzzy_terms,
            semantic_texts=prepared_query.semantic_texts,
            structured_query=prepared_query.structured_query,
            strict_match=False,
            limit=max(len(self.documents), 1),
        )

        return SessionRetrievalFeatures(
            normalized_query=prepared_query.normalized_query,
            corrected_query=prepared_query.corrected_query,
            applied_synonyms=prepared_query.applied_synonyms,
            query_has_correction=float(bool(prepared_query.corrected_query)),
            query_has_synonyms=float(bool(prepared_query.applied_synonyms)),
            features_by_item_id={
                result.document_id: self._result_to_feature_row(result)
                for result in retrieval_results
            },
        )

    def _prepare_query(
        self,
        *,
        query: str,
        normalized_query: str,
    ) -> PreparedQuery:
        source_query = query or normalized_query
        normalized = normalize_query(source_query)
        if not normalized and normalized_query:
            normalized = normalize_query(normalized_query)

        spell_corrected_query = correct_query(normalized, self.spell_corrections)
        fuzzy_corrected_query = (
            None
            if spell_corrected_query
            else correct_query_fuzzy(normalized, self.search_vocabulary)
        )

        layout_corrected_query = correct_keyboard_layout(normalized)
        layout_spell_corrected_query = None
        layout_fuzzy_corrected_query = None
        if layout_corrected_query and not spell_corrected_query and not fuzzy_corrected_query:
            layout_spell_corrected_query = correct_query(
                layout_corrected_query,
                self.spell_corrections,
            )
            layout_fuzzy_corrected_query = (
                layout_spell_corrected_query
                or correct_query_fuzzy(layout_corrected_query, self.search_vocabulary)
            )

        corrected_query = (
            spell_corrected_query
            or fuzzy_corrected_query
            or layout_spell_corrected_query
            or layout_fuzzy_corrected_query
            or layout_corrected_query
        )
        effective_query = corrected_query or normalized
        structured_query = analyze_search_text(effective_query)

        original_query_terms = extract_query_terms(normalized)
        query_terms = extract_query_terms(effective_query)
        expanded_query_terms = expand_term_variants(query_terms)
        expanded_original_query_terms = (
            []
            if original_query_terms == query_terms
            else expand_term_variants(original_query_terms)
        )

        synonym_lookup_terms = list(
            dict.fromkeys(
                [
                    *original_query_terms,
                    *query_terms,
                    *expanded_original_query_terms,
                    *expanded_query_terms,
                ]
            )
        )
        synonym_expansions = self._get_synonym_expansions(synonym_lookup_terms)
        applied_synonyms = list(
            dict.fromkeys(item.synonym for item in synonym_expansions if item.synonym)
        )

        synonym_terms: list[str] = []
        for synonym in applied_synonyms:
            synonym_terms.extend(expand_term_variants(extract_query_terms(synonym)))
        synonym_query_terms = list(dict.fromkeys([*applied_synonyms, *synonym_terms]))

        search_terms = list(
            dict.fromkeys(
                [
                    normalized,
                    effective_query,
                    *original_query_terms,
                    *query_terms,
                    *expanded_original_query_terms,
                    *expanded_query_terms,
                ]
            )
        )
        morphology_terms = self._build_morphology_terms(
            original_query_terms,
            query_terms,
            expanded_original_query_terms,
            expanded_query_terms,
            structured_query.category_hints,
            structured_query.attribute_terms,
        )
        fuzzy_terms = self._build_fuzzy_retrieval_terms(
            base_terms=[
                *original_query_terms,
                *query_terms,
                *expanded_original_query_terms,
                *expanded_query_terms,
            ],
            blocked_terms=search_terms,
        )
        semantic_texts = self._build_semantic_query_texts(
            effective_query,
            normalized,
            extra_values=applied_synonyms,
        )

        return PreparedQuery(
            normalized_query=normalized,
            corrected_query=corrected_query,
            applied_synonyms=applied_synonyms,
            lexical_terms=search_terms,
            morphology_terms=morphology_terms,
            fuzzy_terms=fuzzy_terms,
            synonym_terms=synonym_query_terms,
            semantic_texts=semantic_texts,
            structured_query=structured_query,
        )

    def _get_synonym_expansions(
        self,
        terms: list[str],
    ) -> list[SynonymExpansionRecord]:
        expansions: list[SynonymExpansionRecord] = []
        seen: set[tuple[str, str]] = set()
        for term in terms:
            normalized_term = normalize_query(term)
            for record in self.synonym_map.get(normalized_term, []):
                key = (record.term, record.synonym)
                if key in seen:
                    continue
                seen.add(key)
                expansions.append(record)
        return expansions

    def _build_fuzzy_retrieval_terms(
        self,
        *,
        base_terms: list[str],
        blocked_terms: list[str],
    ) -> list[str]:
        if not base_terms:
            return []

        fuzzy_terms = expand_fuzzy_term_variants(base_terms, self.search_vocabulary)
        expanded_fuzzy_terms = expand_term_variants(fuzzy_terms)
        blocked = set(blocked_terms)

        return list(
            dict.fromkeys(
                term
                for term in [*fuzzy_terms, *expanded_fuzzy_terms]
                if term and term not in blocked
            )
        )

    @staticmethod
    def _build_morphology_terms(*term_groups: list[str]) -> list[str]:
        terms: list[str] = []
        for values in term_groups:
            terms.extend(lemmatize_query_terms(values))
        return list(dict.fromkeys(term for term in terms if term))

    @staticmethod
    def _build_semantic_query_texts(
        *values: str,
        extra_values: list[str] | None = None,
    ) -> list[str]:
        semantic_texts = [value for value in values if value]
        semantic_texts.extend(extra_values or [])
        return list(dict.fromkeys(text for text in semantic_texts if text))

    @staticmethod
    def _result_to_feature_row(result: RetrievalResult) -> dict[str, float]:
        feature_row = {
            "retrieval_score": float(result.score),
            "retrieval_channel_count": float(len(result.channel_scores)),
        }

        for reason_column in RETRIEVAL_REASON_COLUMNS.values():
            feature_row[reason_column] = 0.0
        for reason in result.reasons:
            if reason in RETRIEVAL_REASON_COLUMNS:
                feature_row[RETRIEVAL_REASON_COLUMNS[reason]] = 1.0

        for channel_name in CHANNEL_NAMES:
            feature_row[f"channel_score_{channel_name}"] = float(
                result.channel_scores.get(channel_name, 0.0)
            )
            feature_row[f"channel_rank_{channel_name}"] = float(
                result.channel_ranks.get(channel_name, 0.0)
            )

        for feature_name in RETRIEVAL_FEATURE_COLUMNS:
            feature_row[feature_name] = float(result.features.get(feature_name, 0.0))

        return feature_row


def _safe_json(value: object, *, default: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def _extract_vocab_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token.lower()
        for token in VOCAB_TOKEN_RE.findall(normalize_query(value))
        if len(token) >= 3 and not token.isdigit()
    }
