from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.domain.search.normalizer import extract_query_terms, normalize_query
from app.domain.search.schemas import CandidateItem
from app.integrations.ml.base import RankingProvider, RankingRequest

logger = logging.getLogger(__name__)
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")

DEFAULT_NUMERIC_FEATURES = [
    "query_len",
    "normalized_query_len",
    "position_num",
    "cat_match_user",
    "cat_match_org",
    "supplier_match_user",
    "is_recent_ste",
    "query_in_history",
]

DEFAULT_CATEGORICAL_FEATURES = [
    "item_category_id",
    "item_category_name",
    "item_supplier_id",
    "item_supplier_name",
    "item_status",
]

RETRIEVAL_REASON_FEATURES = [
    "retrieval_exact",
    "retrieval_attribute",
    "retrieval_bm25",
    "retrieval_morphology",
    "retrieval_fuzzy",
    "retrieval_synonym",
    "retrieval_semantic",
    "retrieval_rrf",
]

BASELINE_REASON_FEATURES = [
    "exact_title_match",
    "prefix_title_match",
    "partial_title_match",
    "description_match",
    "token_match",
    "attribute_match",
    "brand_match",
    "numeric_constraint_match",
    "category_match",
    "matches_purchase_history",
    "recent_interaction",
    "popular_supplier",
    "popular_in_organization",
]


class LocalMlRankingProvider(RankingProvider):
    """Local in-process ML reranker supporting CatBoost and legacy linear artifacts."""

    def __init__(self, artifacts_dir: str) -> None:
        self.artifacts_dir = Path(artifacts_dir).expanduser().resolve()
        self.model: Any | None = None
        self.vectorizer: Any | None = None
        self.model_type: str = "none"
        self.numeric_features: list[str] = list(DEFAULT_NUMERIC_FEATURES)
        self.categorical_features: list[str] = list(DEFAULT_CATEGORICAL_FEATURES)
        self.feature_columns: list[str] = [
            *self.numeric_features,
            *self.categorical_features,
        ]

        self._np: Any | None = None
        self._csr_matrix: Any | None = None
        self._hstack: Any | None = None
        self._catboost_pool_cls: Any | None = None
        self.ready = False
        self.supports_cyrillic = True

        self._load_artifacts()

    def _load_artifacts(self) -> None:
        try:
            import numpy as np
        except Exception as exc:
            logger.warning("ML provider disabled: missing numpy dependency (%s)", exc)
            return

        self._np = np

        catboost_path = self.artifacts_dir / "catboost_ranker.cbm"
        if catboost_path.exists():
            if self._load_catboost_artifacts(catboost_path):
                return

        ridge_path = self.artifacts_dir / "ridge_ranker.joblib"
        vectorizer_path = self.artifacts_dir / "tfidf_vectorizer.joblib"
        if ridge_path.exists() and vectorizer_path.exists():
            self._load_linear_artifacts(ridge_path, vectorizer_path)
            return

        logger.warning(
            "ML provider disabled: no supported artifacts found in %s",
            self.artifacts_dir,
        )

    def _load_catboost_artifacts(self, model_path: Path) -> bool:
        try:
            from catboost import CatBoostRanker, Pool
        except Exception as exc:
            logger.warning("CatBoost provider disabled: missing dependency (%s)", exc)
            return False

        model_info_path = self.artifacts_dir / "model_info.json"
        model_info: dict[str, Any] = {}
        if model_info_path.exists():
            try:
                model_info = json.loads(model_info_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("CatBoost provider: failed to read model_info.json (%s)", exc)

        try:
            model = CatBoostRanker()
            model.load_model(str(model_path))
        except Exception as exc:
            logger.warning("CatBoost provider disabled: failed to load model (%s)", exc)
            return False

        self.model = model
        self.model_type = str(model_info.get("model_type") or "catboost_ranker")
        self.numeric_features = list(
            model_info.get("numeric_features") or DEFAULT_NUMERIC_FEATURES
        )
        self.categorical_features = list(
            model_info.get("categorical_features") or DEFAULT_CATEGORICAL_FEATURES
        )
        self.feature_columns = list(
            model_info.get("feature_columns")
            or [*self.numeric_features, *self.categorical_features]
        )
        self._catboost_pool_cls = Pool
        self.ready = True
        self.supports_cyrillic = True
        logger.info("CatBoost ML provider loaded artifacts from %s", self.artifacts_dir)
        return True

    def _load_linear_artifacts(
        self,
        model_path: Path,
        vectorizer_path: Path,
    ) -> None:
        try:
            import joblib
            from scipy.sparse import csr_matrix, hstack
        except Exception as exc:
            logger.warning("Linear ML provider disabled: missing dependencies (%s)", exc)
            return

        numeric_path = self.artifacts_dir / "numeric_features.json"

        try:
            self.model = joblib.load(model_path)
            self.vectorizer = joblib.load(vectorizer_path)
            if numeric_path.exists():
                self.numeric_features = json.loads(
                    numeric_path.read_text(encoding="utf-8")
                )
            self.feature_columns = list(self.numeric_features)
            self._csr_matrix = csr_matrix
            self._hstack = hstack
            self.model_type = "ridge_ranker"
            self.supports_cyrillic = self._detect_cyrillic_support()
            self.ready = True
            logger.info("Linear ML provider loaded artifacts from %s", self.artifacts_dir)
        except Exception as exc:
            logger.warning("Linear ML provider disabled: failed to load artifacts (%s)", exc)
            self.ready = False

    def _detect_cyrillic_support(self) -> bool:
        if self.vectorizer is None:
            return False

        vocabulary = getattr(self.vectorizer, "vocabulary_", None)
        if isinstance(vocabulary, dict):
            tokens = vocabulary.keys()
        else:
            try:
                tokens = self.vectorizer.get_feature_names_out()
            except Exception:
                return True

        return any(self._contains_cyrillic(str(token)) for token in tokens)

    @staticmethod
    def _contains_cyrillic(value: str) -> bool:
        return bool(CYRILLIC_RE.search(value))

    @staticmethod
    def _normalize_values(values: list[str]) -> set[str]:
        normalized: set[str] = set()
        for value in values:
            cleaned = normalize_query(value)
            if cleaned:
                normalized.add(cleaned)
        return normalized

    @staticmethod
    def _token_overlap_count(query_tokens: list[str], text: str) -> float:
        if not query_tokens or not text:
            return 0.0

        candidate_tokens = set(extract_query_terms(text))
        if not candidate_tokens:
            return 0.0

        return float(sum(1 for token in set(query_tokens) if token in candidate_tokens))

    @staticmethod
    def _safe_attributes_text(attributes: dict[str, str]) -> str:
        return " ".join(str(value) for value in attributes.values() if str(value).strip())

    def _build_feature_payloads(
        self,
        request: RankingRequest,
    ) -> tuple[list[str], list[dict[str, float | str]]]:
        text_inputs: list[str] = []
        feature_payloads: list[dict[str, float | str]] = []

        top_categories = self._normalize_values(request.profile.top_categories)
        org_top_categories = self._normalize_values(request.profile.org_top_categories)
        top_suppliers = self._normalize_values(request.profile.top_suppliers)
        popular_queries = self._normalize_values(request.profile.popular_queries)
        recent_ste_ids = set(request.profile.recent_ste_ids)
        popular_ste_ids = set(request.profile.popular_ste_ids)

        original_query = (request.query.original or "").strip()
        normalized_query = (request.query.normalized or "").strip()
        effective_query = (request.query.corrected or normalized_query or original_query).strip()

        normalized_original_query = normalize_query(original_query)
        normalized_query_value = normalize_query(normalized_query)
        normalized_effective_query = normalize_query(effective_query)
        query_tokens = extract_query_terms(normalized_effective_query)

        for position, candidate in enumerate(request.candidates, start=1):
            candidate_title = normalize_query(candidate.title)
            candidate_description = normalize_query(candidate.description)
            candidate_category = normalize_query(candidate.category)
            candidate_supplier = normalize_query(candidate.supplier)
            candidate_attributes_text = self._safe_attributes_text(candidate.attributes)
            candidate_attributes = normalize_query(candidate_attributes_text)

            retrieval_reasons = set(candidate.retrieval_reasons)
            retrieval_channel_scores = dict(candidate.retrieval_channel_scores)
            retrieval_channel_ranks = dict(candidate.retrieval_channel_ranks)
            retrieval_features = dict(candidate.retrieval_features)
            baseline_reasons = set(candidate.reasons)

            title_overlap = self._token_overlap_count(query_tokens, candidate_title)
            description_overlap = self._token_overlap_count(query_tokens, candidate_description)
            attribute_overlap = self._token_overlap_count(query_tokens, candidate_attributes)
            total_overlap = title_overlap + description_overlap + attribute_overlap

            feature_map: dict[str, float | str] = {
                "query_len": float(len(original_query.split())),
                "normalized_query_len": float(len(normalized_query.split())),
                "position_num": float(position),
                "cat_match_user": float(candidate_category in top_categories),
                "cat_match_org": float(candidate_category in org_top_categories),
                "supplier_match_user": float(candidate_supplier in top_suppliers),
                "is_recent_ste": float(candidate.id in recent_ste_ids),
                "query_in_history": float(
                    normalized_query_value in popular_queries
                    or normalized_original_query in popular_queries
                ),
                "baseline_score": float(candidate.baseline_score or candidate.score),
                "retrieval_score": float(candidate.retrieval_score),
                "retrieval_channel_count": float(len(retrieval_channel_scores or retrieval_reasons)),
                "query_has_correction": float(
                    bool(request.query.corrected)
                    and normalize_query(request.query.corrected) != normalized_query_value
                ),
                "query_has_synonyms": float(bool(request.query.applied_synonyms)),
                "query_term_count": float(len(query_tokens)),
                "title_term_overlap": title_overlap,
                "description_term_overlap": description_overlap,
                "attribute_term_overlap": attribute_overlap,
                "total_term_overlap": total_overlap,
                "title_exact_match": float(
                    bool(normalized_effective_query)
                    and candidate_title == normalized_effective_query
                ),
                "title_prefix_match": float(
                    bool(normalized_effective_query)
                    and candidate_title.startswith(normalized_effective_query)
                ),
                "title_partial_match": float(
                    bool(normalized_effective_query)
                    and normalized_effective_query in candidate_title
                ),
                "description_contains_query": float(
                    bool(normalized_effective_query)
                    and normalized_effective_query in candidate_description
                ),
                "matches_purchase_history": float(candidate_category in top_categories),
                "popular_in_organization": float(candidate.id in popular_ste_ids),
                "attribute_value_count": float(len(candidate.attributes)),
                "title_len_chars": float(len(candidate.title)),
                "description_len_chars": float(len(candidate.description)),
                "item_category_id": candidate.category_id,
                "item_category_name": candidate.category,
                "item_supplier_id": candidate.supplier_id,
                "item_supplier_name": candidate.supplier,
                "item_status": candidate.status or "active",
            }

            for feature_name, feature_value in retrieval_features.items():
                feature_map[feature_name] = float(feature_value)

            for channel_name, channel_score in retrieval_channel_scores.items():
                feature_map[f"channel_score_{channel_name}"] = float(channel_score)

            for channel_name, channel_rank in retrieval_channel_ranks.items():
                feature_map[f"channel_rank_{channel_name}"] = float(channel_rank)

            for feature_name in RETRIEVAL_REASON_FEATURES:
                feature_map[feature_name] = float(feature_name in retrieval_reasons)

            for feature_name in BASELINE_REASON_FEATURES:
                feature_map[feature_name] = float(feature_name in baseline_reasons)

            feature_payloads.append(feature_map)

            # Keep serving aligned with the legacy notebook artifacts.
            text_inputs.append(
                " ".join(
                    part
                    for part in [
                        original_query,
                        normalized_query,
                        candidate.category_id,
                        candidate.category,
                        candidate.supplier_id,
                        candidate.supplier,
                        candidate_attributes_text,
                    ]
                    if part
                ).strip()
            )

        return text_inputs, feature_payloads

    def _build_numeric_rows(
        self,
        feature_payloads: list[dict[str, float | str]],
    ) -> list[list[float]]:
        return [
            [float(feature_map.get(name, 0.0)) for name in self.numeric_features]
            for feature_map in feature_payloads
        ]

    def _build_catboost_rows(
        self,
        feature_payloads: list[dict[str, float | str]],
    ) -> list[list[float | str]]:
        rows: list[list[float | str]] = []
        categorical = set(self.categorical_features)

        for feature_map in feature_payloads:
            row: list[float | str] = []
            for column in self.feature_columns:
                default_value: float | str = "" if column in categorical else 0.0
                value = feature_map.get(column, default_value)
                if column in categorical:
                    row.append(str(value))
                else:
                    row.append(float(value))
            rows.append(row)
        return rows

    @staticmethod
    def _minmax(values: Any, np_module: Any) -> Any:
        arr = np_module.asarray(values, dtype=float)
        if arr.size == 0:
            return arr
        low = float(arr.min())
        high = float(arr.max())
        if high - low < 1e-12:
            return np_module.zeros_like(arr)
        return (arr - low) / (high - low)

    @staticmethod
    def _copy_candidate(candidate: CandidateItem, score: float) -> CandidateItem:
        return candidate.model_copy(
            update={
                "score": round(float(score), 4),
                "reasons": list(dict.fromkeys([*candidate.reasons, "ml_rerank"])),
            }
        )

    @staticmethod
    def _baseline_rank(items: list[CandidateItem]) -> list[CandidateItem]:
        return sorted(
            items,
            key=lambda item: (
                item.score,
                item.baseline_score,
                item.retrieval_score,
            ),
            reverse=True,
        )

    def _predict_linear(
        self,
        *,
        text_inputs: list[str],
        feature_payloads: list[dict[str, float | str]],
    ) -> Any:
        if self.vectorizer is None or self._csr_matrix is None or self._hstack is None:
            raise RuntimeError("Linear artifacts are not initialized")

        if not self.supports_cyrillic and any(
            self._contains_cyrillic(text) for text in text_inputs
        ):
            raise ValueError("Artifact vocabulary has no Cyrillic support")

        text_matrix = self.vectorizer.transform(text_inputs)
        numeric_rows = self._build_numeric_rows(feature_payloads)
        num_matrix = self._csr_matrix(self._np.asarray(numeric_rows, dtype=float))
        matrix = self._hstack([text_matrix, num_matrix], format="csr")
        return self.model.predict(matrix)

    def _predict_catboost(
        self,
        *,
        feature_payloads: list[dict[str, float | str]],
    ) -> Any:
        if self._catboost_pool_cls is None:
            raise RuntimeError("CatBoost artifacts are not initialized")

        cat_features = [
            index
            for index, column in enumerate(self.feature_columns)
            if column in set(self.categorical_features)
        ]
        rows = self._build_catboost_rows(feature_payloads)
        pool = self._catboost_pool_cls(
            data=rows,
            cat_features=cat_features,
            feature_names=self.feature_columns,
        )
        return self.model.predict(pool)

    def rank(self, request: RankingRequest) -> list[CandidateItem]:
        if not request.candidates:
            return []

        if not self.ready:
            return self._baseline_rank(request.candidates)

        try:
            text_inputs, feature_payloads = self._build_feature_payloads(request)

            if self.model_type == "catboost_ranker":
                predictions = self._predict_catboost(feature_payloads=feature_payloads)
            else:
                predictions = self._predict_linear(
                    text_inputs=text_inputs,
                    feature_payloads=feature_payloads,
                )

            pred_norm = self._minmax(predictions, self._np)
            baseline_norm = self._minmax(
                [float(item.baseline_score or item.score) for item in request.candidates],
                self._np,
            )
            retrieval_norm = self._minmax(
                [float(item.retrieval_score) for item in request.candidates],
                self._np,
            )

            # Blend learned ranking with stable retrieval and baseline heuristics.
            combined = 0.7 * pred_norm + 0.2 * baseline_norm + 0.1 * retrieval_norm

            reranked = [
                self._copy_candidate(candidate, score)
                for candidate, score in zip(request.candidates, combined, strict=False)
            ]
            return self._baseline_rank(reranked)
        except Exception as exc:
            logger.warning("ML ranking failed, fallback to baseline: %s", exc)
            return self._baseline_rank(request.candidates)
