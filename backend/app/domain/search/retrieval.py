from __future__ import annotations

import logging
import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import AbstractSet, Any, Iterable

import numpy as np

try:  # pragma: no cover - optional dependency for semantic fallback only
    from scipy.sparse import hstack
except ImportError:  # pragma: no cover - lexical retrieval still works without it
    hstack = None

try:  # pragma: no cover - optional dependency for semantic fallback only
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:  # pragma: no cover - lexical retrieval still works without it
    TruncatedSVD = None
    TfidfVectorizer = None

from app.core.config import settings
from app.domain.search.normalizer import (
    extract_query_terms,
    lemmatize_query_terms,
    normalize_query,
)
from app.domain.search.query_analysis import SearchTextAnalysis, analyze_search_text
from app.domain.search.semantic import (
    SEMANTIC_BACKEND_BGE_M3,
    SEMANTIC_BACKEND_FALLBACK,
    build_faiss_index,
    encode_bge_m3_texts,
)

SEMANTIC_BACKEND_DISABLED = "disabled"
LOGGER = logging.getLogger(__name__)

FIELD_NAMES = ("title", "category", "attributes", "description", "supplier")
FIELD_INDEX_TEXT_LIMITS = {
    "title": 512,
    "category": 256,
    "attributes": 4096,
    "description": 4096,
    "supplier": 256,
}
RUNTIME_FIELD_TEXT_NAMES = ("title", "attributes", "description")
RUNTIME_FIELD_TERM_SET_NAMES = ("title", "category", "attributes")
RUNTIME_FIELD_LEMMA_SET_NAMES = ("title", "category")
RETRIEVAL_MIN_CANDIDATE_POOL = 300
RETRIEVAL_MAX_CANDIDATE_POOL = 1200
FIELD_WEIGHTS = {
    "title": 2.4,
    "attributes": 1.55,
    "category": 1.35,
    "description": 0.7,
    "supplier": 0.45,
}
MORPHOLOGY_FIELD_WEIGHTS = {
    "title": 2.15,
    "attributes": 1.45,
    "category": 1.25,
    "description": 0.65,
    "supplier": 0.35,
}
CHANNEL_RRF_WEIGHTS = {
    "exact_structured": 1.45,
    "attribute": 1.2,
    "bm25": 1.2,
    "morphology": 1.0,
    "fuzzy": 0.9,
    "synonym_bm25": 0.8,
    "semantic": 0.8,
}
CHANNEL_REASON_MAP = {
    "exact_structured": "retrieval_exact",
    "attribute": "retrieval_attribute",
    "bm25": "retrieval_bm25",
    "morphology": "retrieval_morphology",
    "fuzzy": "retrieval_fuzzy",
    "synonym_bm25": "retrieval_synonym",
    "semantic": "retrieval_semantic",
}


@dataclass(slots=True)
class SearchDocument:
    id: str
    title: str
    description: str
    category_id: str
    category_name: str
    supplier_id: str
    supplier_name: str
    attributes: dict[str, str] = field(default_factory=dict)
    status: str = "active"
    updated_at: datetime | None = None


@dataclass(slots=True)
class RetrievalResult:
    document_id: str
    score: float
    reasons: list[str] = field(default_factory=list)
    channel_scores: dict[str, float] = field(default_factory=dict)
    channel_ranks: dict[str, int] = field(default_factory=dict)
    features: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class _ChannelHit:
    document_id: str
    score: float
    features: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class _IndexedDocument:
    payload: SearchDocument
    field_texts: dict[str, str]
    field_terms: dict[str, list[str]] | None
    field_term_sets: dict[str, frozenset[str]]
    field_lemma_terms: dict[str, list[str]] | None
    field_lemma_sets: dict[str, frozenset[str]]
    analysis_by_field: dict[str, SearchTextAnalysis] | None
    combined_analysis: "_RuntimeCombinedAnalysis | SearchTextAnalysis"
    title_trigrams: frozenset[str]
    text_trigrams: frozenset[str]
    fuzzy_variants: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class _RuntimeCombinedAnalysis:
    all_terms: frozenset[str]
    token_set: frozenset[str]
    brand_terms: frozenset[str]
    model_terms: frozenset[str]
    code_terms: frozenset[str]
    size_terms: frozenset[str]


class HybridSearchIndex:
    def __init__(
        self,
        documents: Iterable[SearchDocument],
        *,
        enable_semantic: bool = True,
        progress: bool = False,
    ) -> None:
        started_at = time.perf_counter()
        indexed_documents: list[_IndexedDocument] = []
        try:
            total_documents: int | None = len(documents)  # type: ignore[arg-type]
        except TypeError:
            total_documents = None

        for index, document in enumerate(documents, start=1):
            indexed_documents.append(self._index_document(document))
            if progress and (
                index == 1
                or index % 1000 == 0
                or (total_documents is not None and index == total_documents)
            ):
                self._emit_progress(
                    "index-documents",
                    index=index,
                    total=total_documents,
                    started_at=started_at,
                )
        self.documents = indexed_documents
        self.documents_by_id = {
            document.payload.id: document
            for document in indexed_documents
        }
        self.document_ids = [document.payload.id for document in indexed_documents]
        self._position_by_id = {
            document_id: position
            for position, document_id in enumerate(self.document_ids)
        }
        self._all_positions = frozenset(range(len(indexed_documents)))
        self._positions_by_category_id = self._build_position_lookup("category_id")
        self._positions_by_supplier_id = self._build_position_lookup("supplier_id")

        (
            self._bm25_postings,
            self._bm25_doc_lengths,
            self._bm25_avg_doc_length,
            self._bm25_idf,
        ) = self._build_fielded_bm25_index(use_lemmas=False, progress=progress)
        (
            self._lemma_bm25_postings,
            self._lemma_bm25_doc_lengths,
            self._lemma_bm25_avg_doc_length,
            self._lemma_bm25_idf,
        ) = self._build_fielded_bm25_index(use_lemmas=True, progress=progress)

        self._semantic_enabled = False
        self._semantic_backend = SEMANTIC_BACKEND_DISABLED
        self._semantic_faiss_index = None
        self._semantic_word_vectorizer: Any | None = None
        self._semantic_char_vectorizer: Any | None = None
        self._semantic_svd: Any | None = None
        self._semantic_matrix = np.zeros((len(indexed_documents), 0), dtype=float)
        self._release_build_only_state()

        if progress:
            elapsed = time.perf_counter() - started_at
            print(
                "[retrieval-index] ready "
                f"documents={len(indexed_documents)} "
                f"elapsed={_format_progress_seconds(elapsed)}",
                flush=True,
            )

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        state["_semantic_faiss_index"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._disable_semantic_runtime_state()

    def search(
        self,
        *,
        lexical_terms: list[str],
        morphology_terms: list[str],
        synonym_terms: list[str],
        trigram_terms: list[str],
        semantic_texts: list[str],
        structured_query: SearchTextAnalysis | None = None,
        strict_match: bool = False,
        category_id: str | None = None,
        supplier_id: str | None = None,
        allowed_document_ids: set[str] | None = None,
        limit: int = 80,
    ) -> list[RetrievalResult]:
        allowed_positions = self._filter_positions(
            category_id=category_id,
            supplier_id=supplier_id,
            allowed_document_ids=allowed_document_ids,
        )
        if not allowed_positions:
            return []

        lexical_tokens = self._flatten_terms(lexical_terms)
        morphology_tokens = list(dict.fromkeys(token for token in morphology_terms if token))
        synonym_tokens = [
            token
            for token in self._flatten_terms(synonym_terms)
            if token not in set(lexical_tokens)
        ]
        trigram_queries = self._prepare_text_queries(trigram_terms)
        semantic_queries = self._prepare_text_queries(semantic_texts)
        query_analysis = structured_query or analyze_search_text(" ".join(lexical_terms))
        expanded_limit = max(limit * 2, 60)

        if strict_match:
            channel_results: dict[str, list[_ChannelHit]] = {}
            if query_analysis.all_terms:
                channel_results["exact_structured"] = self._retrieve_exact_structured(
                    analysis=query_analysis,
                    allowed_positions=allowed_positions,
                    limit=expanded_limit,
                )
                attribute_hits = self._retrieve_attribute(
                    analysis=query_analysis,
                    allowed_positions=allowed_positions,
                    limit=expanded_limit,
                )
                if attribute_hits:
                    channel_results["attribute"] = attribute_hits

            if lexical_tokens:
                channel_results["bm25"] = self._retrieve_bm25(
                    tokens=lexical_tokens,
                    allowed_positions=allowed_positions,
                    limit=expanded_limit,
                    use_lemmas=False,
                )

            if morphology_tokens:
                channel_results["morphology"] = self._retrieve_bm25(
                    tokens=morphology_tokens,
                    allowed_positions=allowed_positions,
                    limit=expanded_limit,
                    use_lemmas=True,
                )

            return self._rrf_merge(channel_results, limit=limit)

        cheap_channel_results: dict[str, list[_ChannelHit]] = {}

        if lexical_tokens:
            cheap_channel_results["bm25"] = self._retrieve_bm25(
                tokens=lexical_tokens,
                allowed_positions=allowed_positions,
                limit=expanded_limit,
                use_lemmas=False,
            )

        if morphology_tokens:
            cheap_channel_results["morphology"] = self._retrieve_bm25(
                tokens=morphology_tokens,
                allowed_positions=allowed_positions,
                limit=expanded_limit,
                use_lemmas=True,
            )

        if synonym_tokens:
            cheap_channel_results["synonym_bm25"] = self._retrieve_bm25(
                tokens=synonym_tokens,
                allowed_positions=allowed_positions,
                limit=expanded_limit,
                use_lemmas=False,
            )

        if self._semantic_enabled and semantic_queries:
            cheap_channel_results["semantic"] = self._retrieve_semantic(
                queries=semantic_queries,
                allowed_positions=allowed_positions,
                limit=expanded_limit,
            )

        candidate_pool_limit = min(
            RETRIEVAL_MAX_CANDIDATE_POOL,
            max(limit * 8, RETRIEVAL_MIN_CANDIDATE_POOL),
        )
        shortlist_results = self._rrf_merge(
            cheap_channel_results,
            limit=candidate_pool_limit,
        )
        shortlist_positions = {
            self._position_by_id[result.document_id]
            for result in shortlist_results
            if result.document_id in self._position_by_id
        }

        if not shortlist_positions and trigram_queries:
            fuzzy_fallback = self._retrieve_fuzzy(
                queries=trigram_queries,
                allowed_positions=allowed_positions,
                limit=candidate_pool_limit,
            )
            shortlist_positions = {
                self._position_by_id[hit.document_id]
                for hit in fuzzy_fallback
                if hit.document_id in self._position_by_id
            }
            if fuzzy_fallback:
                cheap_channel_results["fuzzy"] = fuzzy_fallback

        if not shortlist_positions:
            return shortlist_results[:limit]

        shortlist_channel_results = {
            channel_name: [
                hit
                for hit in ranking
                if self._position_by_id.get(hit.document_id) in shortlist_positions
            ]
            for channel_name, ranking in cheap_channel_results.items()
            if ranking
        }

        if query_analysis.all_terms:
            shortlist_channel_results["exact_structured"] = self._retrieve_exact_structured(
                analysis=query_analysis,
                allowed_positions=shortlist_positions,
                limit=expanded_limit,
            )
            attribute_hits = self._retrieve_attribute(
                analysis=query_analysis,
                allowed_positions=shortlist_positions,
                limit=expanded_limit,
            )
            if attribute_hits:
                shortlist_channel_results["attribute"] = attribute_hits

        if trigram_queries and "fuzzy" not in shortlist_channel_results:
            fuzzy_hits = self._retrieve_fuzzy(
                queries=trigram_queries,
                allowed_positions=shortlist_positions,
                limit=expanded_limit,
            )
            if fuzzy_hits:
                shortlist_channel_results["fuzzy"] = fuzzy_hits

        return self._rrf_merge(shortlist_channel_results, limit=limit)

    @staticmethod
    def _index_document(document: SearchDocument) -> _IndexedDocument:
        attributes_text = " ".join(
            f"{key} {value}".strip()
            for key, value in document.attributes.items()
            if key or value
        )
        raw_field_texts = {
            "title": document.title,
            "category": document.category_name,
            "attributes": attributes_text,
            "description": document.description,
            "supplier": document.supplier_name,
        }
        field_texts = {
            field_name: normalize_query(raw_value[: FIELD_INDEX_TEXT_LIMITS[field_name]])
            for field_name, raw_value in raw_field_texts.items()
        }

        field_terms = {
            field_name: extract_query_terms(text, deduplicate=False)
            for field_name, text in field_texts.items()
        }
        field_lemma_terms = {
            field_name: lemmatize_query_terms(tokens, deduplicate=False)
            for field_name, tokens in field_terms.items()
        }
        analysis_by_field = {
            field_name: analyze_search_text(text)
            for field_name, text in field_texts.items()
        }
        combined_text = " ".join(text for text in field_texts.values() if text)
        combined_analysis = analyze_search_text(combined_text)

        fuzzy_variants = tuple(
            dict.fromkeys(
                item
                for item in [
                    field_texts["title"],
                    field_texts["attributes"],
                    *field_terms["title"],
                    *field_terms["attributes"],
                    *analysis_by_field["title"].brand_terms,
                    *analysis_by_field["title"].model_terms,
                    *analysis_by_field["title"].size_terms,
                ]
                if item
            )
        )

        return _IndexedDocument(
            payload=document,
            field_texts=field_texts,
            field_terms=field_terms,
            field_term_sets={
                field_name: frozenset(tokens)
                for field_name, tokens in field_terms.items()
            },
            field_lemma_terms=field_lemma_terms,
            field_lemma_sets={
                field_name: frozenset(tokens)
                for field_name, tokens in field_lemma_terms.items()
            },
            analysis_by_field=analysis_by_field,
            combined_analysis=combined_analysis,
            title_trigrams=_build_trigrams(field_texts["title"]),
            text_trigrams=_build_trigrams(combined_text),
            fuzzy_variants=fuzzy_variants,
        )

    @staticmethod
    def _flatten_terms(values: Iterable[str]) -> list[str]:
        tokens: list[str] = []
        for value in values:
            tokens.extend(extract_query_terms(value, deduplicate=False))
        return list(dict.fromkeys(token for token in tokens if token))

    @staticmethod
    def _prepare_text_queries(values: Iterable[str]) -> list[str]:
        prepared: list[str] = []
        for value in values:
            normalized = normalize_query(value)
            if normalized:
                prepared.append(normalized)
        return list(dict.fromkeys(prepared))

    def _filter_positions(
        self,
        *,
        category_id: str | None,
        supplier_id: str | None,
        allowed_document_ids: set[str] | None = None,
    ) -> set[int]:
        if allowed_document_ids is None:
            positions: AbstractSet[int] = self._all_positions
        else:
            positions = {
                self._position_by_id[document_id]
                for document_id in allowed_document_ids
                if document_id in self._position_by_id
            }
            if not positions:
                return set()

        if category_id:
            category_positions = self._positions_by_category_id.get(category_id)
            if not category_positions:
                return set()
            positions = positions & category_positions
            if not positions:
                return set()

        if supplier_id:
            supplier_positions = self._positions_by_supplier_id.get(supplier_id)
            if not supplier_positions:
                return set()
            positions = positions & supplier_positions
            if not positions:
                return set()

        return set(positions)

    def _build_fielded_bm25_index(
        self,
        *,
        use_lemmas: bool,
        progress: bool = False,
    ) -> tuple[
        dict[str, dict[str, list[tuple[int, int]]]],
        dict[str, np.ndarray],
        dict[str, float],
        dict[str, dict[str, float]],
    ]:
        postings = {
            field_name: defaultdict(list)
            for field_name in FIELD_NAMES
        }
        doc_lengths = {
            field_name: np.zeros(len(self.documents), dtype=float)
            for field_name in FIELD_NAMES
        }
        avg_doc_lengths: dict[str, float] = {}
        idf_by_field: dict[str, dict[str, float]] = {}

        if not self.documents:
            return postings, doc_lengths, avg_doc_lengths, idf_by_field

        document_count = max(len(self.documents), 1)
        bm25_started_at = time.perf_counter()

        for field_index, field_name in enumerate(FIELD_NAMES, start=1):
            document_frequencies: Counter[str] = Counter()
            for position, document in enumerate(self.documents):
                term_map = (
                    document.field_lemma_terms
                    if use_lemmas
                    else document.field_terms
                )
                if term_map is None:
                    raise RuntimeError("Build-time token state is not available for BM25 indexing")
                tokens = term_map[field_name]
                term_counts = Counter(tokens)
                doc_lengths[field_name][position] = float(sum(term_counts.values()))
                for token, term_frequency in term_counts.items():
                    postings[field_name][token].append((position, term_frequency))
                document_frequencies.update(term_counts.keys())

            avg_doc_lengths[field_name] = float(
                doc_lengths[field_name].mean() if doc_lengths[field_name].size else 0.0
            )
            idf_by_field[field_name] = {}
            for token, frequency in document_frequencies.items():
                numerator = document_count - frequency + 0.5
                denominator = frequency + 0.5
                idf_by_field[field_name][token] = math.log1p(numerator / denominator)

            if progress:
                mode = "lemma" if use_lemmas else "lexical"
                elapsed = time.perf_counter() - bm25_started_at
                print(
                    "[retrieval-index] bm25 "
                    f"mode={mode} "
                    f"field={field_name} "
                    f"{field_index}/{len(FIELD_NAMES)} "
                    f"elapsed={_format_progress_seconds(elapsed)}",
                    flush=True,
                )

        return postings, doc_lengths, avg_doc_lengths, idf_by_field

    @staticmethod
    def _emit_progress(
        stage: str,
        *,
        index: int,
        total: int | None,
        started_at: float,
    ) -> None:
        elapsed = time.perf_counter() - started_at
        rate = index / elapsed if elapsed > 0 else 0.0
        remaining = (
            ((total - index) / rate)
            if rate > 0 and total is not None
            else 0.0
        )
        if total is None:
            print(
                "[retrieval-index] "
                f"{stage} "
                f"count={index} "
                f"elapsed={_format_progress_seconds(elapsed)}",
                flush=True,
            )
            return

        print(
            "[retrieval-index] "
            f"{stage} "
            f"{index}/{total} "
            f"({(index / max(total, 1)) * 100:.1f}%) "
            f"elapsed={_format_progress_seconds(elapsed)} "
            f"eta={_format_progress_seconds(remaining)}",
            flush=True,
        )

    def _build_position_lookup(self, attribute_name: str) -> dict[str, frozenset[int]]:
        positions_by_value: dict[str, set[int]] = defaultdict(set)
        for position, document in enumerate(self.documents):
            value = getattr(document.payload, attribute_name, "")
            if value:
                positions_by_value[str(value)].add(position)
        return {
            value: frozenset(positions)
            for value, positions in positions_by_value.items()
        }

    def _build_semantic_index(self) -> None:
        if not self.documents:
            return

        semantic_corpus = [
            self._build_semantic_document_text(document)
            for document in self.documents
        ]
        if self._build_bge_semantic_index(semantic_corpus):
            return

        self._build_fallback_semantic_index(semantic_corpus)

    def _release_build_only_state(self) -> None:
        for document in self.documents:
            document.field_texts = {
                field_name: document.field_texts.get(field_name, "")
                for field_name in RUNTIME_FIELD_TEXT_NAMES
            }
            document.field_term_sets = {
                field_name: document.field_term_sets.get(field_name, frozenset())
                for field_name in RUNTIME_FIELD_TERM_SET_NAMES
            }
            document.field_lemma_sets = {
                field_name: document.field_lemma_sets.get(field_name, frozenset())
                for field_name in RUNTIME_FIELD_LEMMA_SET_NAMES
            }
            document.field_terms = None
            document.field_lemma_terms = None
            document.analysis_by_field = None
            document.combined_analysis = _to_runtime_combined_analysis(document.combined_analysis)
            document.payload.title = ""
            document.payload.description = ""
            document.payload.category_name = ""
            document.payload.supplier_name = ""
            document.payload.attributes = {}
            document.payload.status = ""

    @staticmethod
    def _build_semantic_document_text(document: _IndexedDocument) -> str:
        attributes_text = "; ".join(
            f"{key} {value}".strip()
            for key, value in document.payload.attributes.items()
            if key or value
        )
        return " ".join(
            part
            for part in [
                document.payload.title,
                document.payload.title,
                f"категория {document.payload.category_name}".strip(),
                f"атрибуты {attributes_text}".strip() if attributes_text else "",
                document.payload.description,
            ]
            if part
        )

    def _build_bge_semantic_index(self, semantic_corpus: list[str]) -> bool:
        preferred_backend = settings.search_semantic_backend.strip().lower()
        if preferred_backend not in {"auto", SEMANTIC_BACKEND_BGE_M3}:
            return False

        dense_embeddings = encode_bge_m3_texts(semantic_corpus)
        if dense_embeddings is None or dense_embeddings.size == 0:
            return False

        self._semantic_backend = SEMANTIC_BACKEND_BGE_M3
        self._semantic_matrix = dense_embeddings
        self._semantic_faiss_index = build_faiss_index(dense_embeddings)
        self._semantic_word_vectorizer = None
        self._semantic_char_vectorizer = None
        self._semantic_svd = None
        return True

    def _build_fallback_semantic_index(self, semantic_corpus: list[str]) -> None:
        if TfidfVectorizer is None or hstack is None:
            LOGGER.warning(
                "Semantic fallback is disabled because scipy/sklearn are not installed."
            )
            self._semantic_backend = SEMANTIC_BACKEND_DISABLED
            self._semantic_matrix = np.zeros((len(self.documents), 0), dtype=float)
            self._semantic_faiss_index = None
            self._semantic_word_vectorizer = None
            self._semantic_char_vectorizer = None
            self._semantic_svd = None
            return

        self._semantic_backend = SEMANTIC_BACKEND_FALLBACK

        self._semantic_word_vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        self._semantic_char_vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
            sublinear_tf=True,
        )

        word_matrix = self._semantic_word_vectorizer.fit_transform(semantic_corpus)
        char_matrix = self._semantic_char_vectorizer.fit_transform(semantic_corpus)
        semantic_matrix = hstack([word_matrix, char_matrix], format="csr")

        max_components = min(
            128,
            semantic_matrix.shape[0] - 1,
            semantic_matrix.shape[1] - 1,
        )
        if max_components >= 2:
            self._semantic_svd = TruncatedSVD(
                n_components=max_components,
                random_state=42,
            )
            dense = self._semantic_svd.fit_transform(semantic_matrix)
        else:
            dense = semantic_matrix.toarray()

        self._semantic_matrix = _l2_normalize(dense)
        self._semantic_faiss_index = None

    def _disable_semantic_runtime_state(self) -> None:
        self._semantic_enabled = False
        self._semantic_backend = SEMANTIC_BACKEND_DISABLED
        self._semantic_faiss_index = None
        self._semantic_word_vectorizer = None
        self._semantic_char_vectorizer = None
        self._semantic_svd = None
        self._semantic_matrix = np.zeros((len(self.documents), 0), dtype=float)

    def _retrieve_bm25(
        self,
        *,
        tokens: list[str],
        allowed_positions: AbstractSet[int],
        limit: int,
        use_lemmas: bool,
    ) -> list[_ChannelHit]:
        if not tokens:
            return []

        postings = self._lemma_bm25_postings if use_lemmas else self._bm25_postings
        doc_lengths = self._lemma_bm25_doc_lengths if use_lemmas else self._bm25_doc_lengths
        avg_doc_lengths = (
            self._lemma_bm25_avg_doc_length if use_lemmas else self._bm25_avg_doc_length
        )
        idf_by_field = self._lemma_bm25_idf if use_lemmas else self._bm25_idf
        field_weights = MORPHOLOGY_FIELD_WEIGHTS if use_lemmas else FIELD_WEIGHTS

        scores: dict[int, float] = defaultdict(float)
        token_weights = Counter(tokens)
        k1 = 1.45
        b = 0.72

        for token, query_frequency in token_weights.items():
            query_weight = 1.0 + math.log1p(query_frequency)
            for field_name, field_weight in field_weights.items():
                field_postings = postings[field_name].get(token)
                if not field_postings:
                    continue

                idf = idf_by_field[field_name].get(token, 0.0)
                avg_doc_length = max(avg_doc_lengths.get(field_name, 0.0), 1.0)
                for position, term_frequency in field_postings:
                    if position not in allowed_positions:
                        continue
                    doc_length = doc_lengths[field_name][position]
                    denominator = term_frequency + k1 * (
                        1 - b + b * (doc_length / avg_doc_length)
                    )
                    scores[position] += field_weight * idf * (
                        term_frequency * (k1 + 1) / max(denominator, 1e-6)
                    ) * query_weight

        return self._sort_channel_scores(scores, limit=limit)

    def _retrieve_exact_structured(
        self,
        *,
        analysis: SearchTextAnalysis,
        allowed_positions: AbstractSet[int],
        limit: int,
    ) -> list[_ChannelHit]:
        if not analysis.normalized_text:
            return []

        scores: dict[int, float] = {}
        features_by_position: dict[int, dict[str, float]] = {}

        query_term_set = analysis.text_term_set
        query_lemma_set = analysis.lemma_term_set
        category_hint_set = analysis.category_hint_set
        attribute_term_set = analysis.attribute_term_set
        brand_term_set = analysis.brand_term_set
        model_term_set = analysis.model_term_set
        code_term_set = analysis.code_term_set
        size_term_set = analysis.size_term_set
        quantity_constraints = analysis.quantity_constraints
        strict_terms = analysis.strict_terms

        for position in allowed_positions:
            document = self.documents[position]
            score = 0.0
            feature_map: dict[str, float] = {}
            title_text = document.field_texts["title"]
            attributes_text = document.field_texts["attributes"]
            description_text = document.field_texts["description"]

            if analysis.normalized_text == title_text:
                score += 1.55
                feature_map["exact_match_flag"] = 1.0
                feature_map["phrase_match_flag"] = 1.0
            elif title_text.startswith(analysis.normalized_text):
                score += 1.2
                feature_map["phrase_match_flag"] = 1.0
            elif any(phrase and phrase in title_text for phrase in analysis.phrase_queries):
                score += 0.95
                feature_map["phrase_match_flag"] = 1.0
            elif any(
                phrase and phrase in attributes_text
                for phrase in analysis.phrase_queries
            ):
                score += 0.72
                feature_map["phrase_match_flag"] = 1.0
            elif any(
                phrase and phrase in description_text
                for phrase in analysis.phrase_queries
            ):
                score += 0.32

            title_overlap = len(query_term_set & document.field_term_sets["title"])
            attribute_overlap = len(attribute_term_set & document.field_term_sets["attributes"])
            lemma_overlap = len(query_lemma_set & document.field_lemma_sets["title"])
            if title_overlap:
                score += min(title_overlap * 0.16, 0.48)
            if lemma_overlap:
                score += min(lemma_overlap * 0.1, 0.2)
            if attribute_overlap:
                score += min(attribute_overlap * 0.2, 0.8)
                feature_map["attribute_overlap_count"] = float(attribute_overlap)

            category_matches = 0
            if category_hint_set:
                category_matches = len(
                    category_hint_set
                    & (
                        document.field_term_sets["title"]
                        | document.field_term_sets["category"]
                        | document.field_lemma_sets["title"]
                        | document.field_lemma_sets["category"]
                    )
                )
                if category_matches:
                    score += min(category_matches * 0.17, 0.51)
                    feature_map["category_match_flag"] = 1.0

            brand_matches = len(brand_term_set & document.combined_analysis.brand_terms)
            if brand_matches:
                score += 0.36 + min(brand_matches * 0.12, 0.24)
                feature_map["brand_match_flag"] = 1.0

            model_matches = len(model_term_set & document.combined_analysis.model_terms)
            if model_matches:
                score += 0.42 + min(model_matches * 0.12, 0.3)

            code_matches = len(code_term_set & document.combined_analysis.code_terms)
            if code_matches:
                score += 0.35 + min(code_matches * 0.1, 0.2)

            size_matches = len(size_term_set & document.combined_analysis.size_terms)
            if size_matches:
                score += 0.28 + min(size_matches * 0.12, 0.24)

            numeric_matches = _count_matching_constraints(quantity_constraints, document)
            if quantity_constraints:
                feature_map["numeric_constraint_match_flag"] = float(
                    numeric_matches == len(quantity_constraints)
                )
                if numeric_matches:
                    score += min(numeric_matches * 0.28, 0.84)

            strict_match_count = 0
            combined_terms = document.combined_analysis.all_terms
            for term in strict_terms:
                if term in combined_terms:
                    strict_match_count += 1
            strict_coverage = (
                strict_match_count / max(len(strict_terms), 1)
                if strict_terms
                else 0.0
            )
            if strict_terms:
                score += strict_coverage * (0.8 if analysis.is_hard_query else 0.35)
                feature_map["strict_term_coverage"] = round(strict_coverage, 4)

            if analysis.is_hard_query and strict_terms and strict_coverage < 0.34:
                continue

            if score < 0.24:
                continue

            scores[position] = score
            features_by_position[position] = feature_map

        return self._sort_channel_scores(
            scores,
            limit=limit,
            features_by_position=features_by_position,
        )

    def _retrieve_attribute(
        self,
        *,
        analysis: SearchTextAnalysis,
        allowed_positions: AbstractSet[int],
        limit: int,
    ) -> list[_ChannelHit]:
        if (
            not analysis.attribute_terms
            and not analysis.category_hints
            and not analysis.quantity_constraints
        ):
            return []

        scores: dict[int, float] = {}
        features_by_position: dict[int, dict[str, float]] = {}
        attribute_term_set = analysis.attribute_term_set
        category_hint_set = analysis.category_hint_set

        for position in allowed_positions:
            document = self.documents[position]
            score = 0.0
            feature_map: dict[str, float] = {}

            attribute_overlap = len(
                attribute_term_set
                & (
                    document.field_term_sets["attributes"]
                    | document.field_term_sets["title"]
                    | document.field_term_sets["category"]
                )
            )
            if attribute_overlap:
                score += min(attribute_overlap * 0.34, 1.02)
                feature_map["attribute_overlap_count"] = float(attribute_overlap)

            category_overlap = len(
                category_hint_set
                & (
                    document.field_term_sets["category"]
                    | document.field_term_sets["title"]
                    | document.field_lemma_sets["category"]
                    | document.field_lemma_sets["title"]
                )
            )
            if category_overlap:
                score += min(category_overlap * 0.22, 0.66)
                feature_map["category_match_flag"] = 1.0

            numeric_matches = _count_matching_constraints(
                analysis.quantity_constraints,
                document,
            )
            if analysis.quantity_constraints and numeric_matches:
                score += min(numeric_matches * 0.28, 0.84)
                feature_map["numeric_constraint_match_flag"] = float(
                    numeric_matches == len(analysis.quantity_constraints)
                )

            if score < 0.2:
                continue

            scores[position] = score
            features_by_position[position] = feature_map

        return self._sort_channel_scores(
            scores,
            limit=limit,
            features_by_position=features_by_position,
        )

    def _retrieve_fuzzy(
        self,
        *,
        queries: list[str],
        allowed_positions: AbstractSet[int],
        limit: int,
    ) -> list[_ChannelHit]:
        if not queries:
            return []

        query_trigrams = [
            (query, _build_trigrams(query))
            for query in queries
            if len(query) >= 3
        ]
        if not query_trigrams:
            return []

        shortlist: list[tuple[int, float]] = []
        for position in allowed_positions:
            document = self.documents[position]
            best_trigram_score = 0.0
            for _, query_trigram in query_trigrams:
                title_score = _trigram_similarity(query_trigram, document.title_trigrams) * 1.18
                text_score = _trigram_similarity(query_trigram, document.text_trigrams)
                best_trigram_score = max(best_trigram_score, title_score, text_score)
            if best_trigram_score >= 0.13:
                shortlist.append((position, best_trigram_score))

        shortlist.sort(key=lambda item: item[1], reverse=True)
        shortlist = shortlist[: max(limit * 6, 90)]

        scores: dict[int, float] = {}
        features_by_position: dict[int, dict[str, float]] = {}
        for position, trigram_score in shortlist:
            document = self.documents[position]
            edit_score = max(
                (
                    _edit_similarity(query, candidate)
                    for query in queries
                    for candidate in document.fuzzy_variants
                    if candidate
                ),
                default=0.0,
            )
            combined_score = (trigram_score * 0.58) + (edit_score * 0.42)
            if edit_score < 0.52 and combined_score < 0.24:
                continue

            scores[position] = combined_score
            features_by_position[position] = {
                "fuzzy_edit_score": round(edit_score, 4),
            }

        return self._sort_channel_scores(
            scores,
            limit=limit,
            features_by_position=features_by_position,
        )

    def _retrieve_semantic(
        self,
        *,
        queries: list[str],
        allowed_positions: AbstractSet[int],
        limit: int,
    ) -> list[_ChannelHit]:
        if not queries or self._semantic_matrix.size == 0:
            return []

        query_vector = self._encode_semantic_query(queries)
        if query_vector is None or query_vector.size == 0:
            return []

        scores: dict[int, float] = {}
        features_by_position: dict[int, dict[str, float]] = {}
        min_score = self._semantic_min_score()

        if (
            self._semantic_backend == SEMANTIC_BACKEND_BGE_M3
            and self._semantic_faiss_index is not None
            and len(allowed_positions) == len(self.documents)
        ):
            faiss_scores = self._search_semantic_with_faiss(
                query_vector=query_vector,
                limit=limit,
            )
            for position, score in faiss_scores:
                if score < min_score:
                    continue
                scores[position] = score
                features_by_position[position] = self._semantic_backend_features(use_faiss=True)
        else:
            similarities = self._semantic_matrix @ query_vector.T
            raw_scores = similarities.reshape(-1)
            for position in allowed_positions:
                score = float(raw_scores[position])
                if score < min_score:
                    continue
                scores[position] = score
                features_by_position[position] = self._semantic_backend_features(use_faiss=False)

        return self._sort_channel_scores(
            scores,
            limit=limit,
            features_by_position=features_by_position,
        )

    def _encode_semantic_query(self, queries: list[str]) -> np.ndarray | None:
        query_text = " ".join(dict.fromkeys(queries))
        if not query_text:
            return None

        if self._semantic_backend == SEMANTIC_BACKEND_BGE_M3:
            return encode_bge_m3_texts([query_text])

        if (
            self._semantic_word_vectorizer is None
            or self._semantic_char_vectorizer is None
        ):
            return None

        word_vector = self._semantic_word_vectorizer.transform([query_text])
        char_vector = self._semantic_char_vectorizer.transform([query_text])
        sparse_query = hstack([word_vector, char_vector], format="csr")

        if self._semantic_svd is not None:
            dense_query = self._semantic_svd.transform(sparse_query)
        else:
            dense_query = sparse_query.toarray()

        return _l2_normalize(dense_query)

    def _search_semantic_with_faiss(
        self,
        *,
        query_vector: np.ndarray,
        limit: int,
    ) -> list[tuple[int, float]]:
        candidate_pool = min(
            len(self.documents),
            max(limit * 8, settings.search_semantic_candidate_pool),
        )
        if candidate_pool <= 0:
            return []

        raw_scores, raw_positions = self._semantic_faiss_index.search(  # type: ignore[union-attr]
            np.ascontiguousarray(query_vector.astype(np.float32)),
            candidate_pool,
        )
        return [
            (int(position), float(score))
            for score, position in zip(raw_scores[0], raw_positions[0], strict=False)
            if position >= 0
        ]

    def _semantic_min_score(self) -> float:
        if self._semantic_backend == SEMANTIC_BACKEND_BGE_M3:
            return settings.search_semantic_dense_min_score
        return settings.search_semantic_fallback_min_score

    def _semantic_backend_features(self, *, use_faiss: bool) -> dict[str, float]:
        features = {
            "semantic_backend_bge_m3": float(
                self._semantic_backend == SEMANTIC_BACKEND_BGE_M3
            ),
            "semantic_backend_fallback": float(
                self._semantic_backend == SEMANTIC_BACKEND_FALLBACK
            ),
        }
        if use_faiss:
            features["semantic_via_faiss"] = 1.0
        return features

    def _rrf_merge(
        self,
        channel_results: dict[str, list[_ChannelHit]],
        *,
        limit: int,
    ) -> list[RetrievalResult]:
        if not channel_results:
            return []

        k = 60
        fused_scores: dict[str, float] = defaultdict(float)
        channel_scores_by_id: dict[str, dict[str, float]] = defaultdict(dict)
        channel_ranks_by_id: dict[str, dict[str, int]] = defaultdict(dict)
        feature_map_by_id: dict[str, dict[str, float]] = defaultdict(dict)

        for channel_name, ranking in channel_results.items():
            channel_weight = CHANNEL_RRF_WEIGHTS.get(channel_name, 1.0)
            for rank, hit in enumerate(ranking, start=1):
                fused_scores[hit.document_id] += channel_weight / (k + rank)
                channel_scores_by_id[hit.document_id][channel_name] = round(hit.score, 4)
                channel_ranks_by_id[hit.document_id][channel_name] = rank
                feature_map_by_id[hit.document_id][f"channel_hit_{channel_name}"] = 1.0
                for feature_name, feature_value in hit.features.items():
                    current = feature_map_by_id[hit.document_id].get(feature_name, 0.0)
                    feature_map_by_id[hit.document_id][feature_name] = max(
                        current,
                        float(feature_value),
                    )

        max_rrf_score = sum(CHANNEL_RRF_WEIGHTS.values()) / (k + 1)
        results: list[RetrievalResult] = []

        for document_id, fused_score in fused_scores.items():
            channel_hits = channel_scores_by_id[document_id]
            feature_map = feature_map_by_id[document_id]
            feature_map["retrieval_channel_count"] = float(len(channel_hits))
            feature_map["appeared_in_multiple_channels"] = float(len(channel_hits) >= 2)
            reasons = [
                CHANNEL_REASON_MAP[channel_name]
                for channel_name in channel_hits
                if channel_name in CHANNEL_REASON_MAP
            ]
            if len(channel_hits) >= 2:
                reasons.append("retrieval_rrf")

            results.append(
                RetrievalResult(
                    document_id=document_id,
                    score=round(min(fused_score / max(max_rrf_score, 1e-6), 1.0), 4),
                    reasons=list(dict.fromkeys(reasons)),
                    channel_scores=channel_hits,
                    channel_ranks=channel_ranks_by_id[document_id],
                    features=feature_map,
                )
            )

        results.sort(
            key=lambda result: (
                result.score,
                len(result.channel_scores),
                max(result.channel_scores.values(), default=0.0),
                self._document_sort_key(result.document_id),
            ),
            reverse=True,
        )
        return results[:limit]

    def _sort_channel_scores(
        self,
        scores: dict[int, float],
        *,
        limit: int,
        features_by_position: dict[int, dict[str, float]] | None = None,
    ) -> list[_ChannelHit]:
        ranked = sorted(
            (
                (position, float(score))
                for position, score in scores.items()
                if score > 0
            ),
            key=lambda item: (
                item[1],
                self._document_sort_key(self.document_ids[item[0]]),
            ),
            reverse=True,
        )
        return [
            _ChannelHit(
                document_id=self.document_ids[position],
                score=score,
                features=(features_by_position or {}).get(position, {}),
            )
            for position, score in ranked[:limit]
        ]

    def _document_sort_key(self, document_id: str) -> float:
        position = self._position_by_id[document_id]
        updated_at = self.documents[position].payload.updated_at
        if updated_at is None:
            return 0.0
        return updated_at.timestamp()


def _count_matching_constraints(
    constraints: list,
    document: _IndexedDocument,
) -> int:
    if not constraints:
        return 0

    matches = 0
    document_terms = document.combined_analysis.all_terms
    document_tokens = document.combined_analysis.token_set
    for constraint in constraints:
        if constraint.normalized in document_terms:
            matches += 1
            continue
        if constraint.value in document_tokens and constraint.unit in document_terms:
            matches += 1
    return matches


def _to_runtime_combined_analysis(
    analysis: SearchTextAnalysis | _RuntimeCombinedAnalysis,
) -> _RuntimeCombinedAnalysis:
    if isinstance(analysis, _RuntimeCombinedAnalysis):
        return analysis
    return _RuntimeCombinedAnalysis(
        all_terms=analysis.all_term_set,
        token_set=analysis.token_set,
        brand_terms=analysis.brand_term_set,
        model_terms=analysis.model_term_set,
        code_terms=analysis.code_term_set,
        size_terms=analysis.size_term_set,
    )


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    safe_norms = np.where(norms > 0, norms, 1.0)
    return matrix / safe_norms


def _format_progress_seconds(value: float) -> str:
    total_seconds = max(int(value), 0)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _build_trigrams(value: str) -> frozenset[str]:
    normalized = normalize_query(value)
    if not normalized:
        return frozenset()

    padded = f"  {normalized} "
    return frozenset(padded[index : index + 3] for index in range(len(padded) - 2))


def _trigram_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0

    overlap = len(left & right)
    return (2.0 * overlap) / (len(left) + len(right))


def _edit_similarity(left: str, right: str) -> float:
    distance = _damerau_levenshtein_distance(left, right)
    max_len = max(len(left), len(right), 1)
    return max(0.0, 1.0 - (distance / max_len))


def _damerau_levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    distances = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    for index in range(len(left) + 1):
        distances[index][0] = index
    for index in range(len(right) + 1):
        distances[0][index] = index

    for left_index in range(1, len(left) + 1):
        for right_index in range(1, len(right) + 1):
            cost = 0 if left[left_index - 1] == right[right_index - 1] else 1
            distances[left_index][right_index] = min(
                distances[left_index - 1][right_index] + 1,
                distances[left_index][right_index - 1] + 1,
                distances[left_index - 1][right_index - 1] + cost,
            )
            if (
                left_index > 1
                and right_index > 1
                and left[left_index - 1] == right[right_index - 2]
                and left[left_index - 2] == right[right_index - 1]
            ):
                distances[left_index][right_index] = min(
                    distances[left_index][right_index],
                    distances[left_index - 2][right_index - 2] + cost,
                )

    return distances[len(left)][len(right)]
