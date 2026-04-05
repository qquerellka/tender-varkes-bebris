import unittest

import numpy as np
from scipy.sparse import csr_matrix, hstack

from app.domain.personalization.schemas import SearchProfileRead
from app.domain.search.schemas import CandidateItem, CurrentActor
from app.integrations.ml.base import RankingQueryContext, RankingRequest
from app.integrations.ml.local import LocalMlRankingProvider


QUERY_TEXT = "\u043e\u0444\u0438\u0441\u043d\u0430\u044f \u0431\u0443\u043c\u0430\u0433\u0430 80"
QUERY_SYNONYM = "\u0431\u0443\u043c\u0430\u0433\u0430 \u0434\u043b\u044f \u043f\u0435\u0447\u0430\u0442\u0438"
CATEGORY_NAME = "\u041e\u0444\u0438\u0441"
SUPPLIER_ONE = "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a 1"
SUPPLIER_TWO = "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a 2"
TITLE_ONE = "\u041e\u0444\u0438\u0441\u043d\u0430\u044f \u0431\u0443\u043c\u0430\u0433\u0430 \u041080"
TITLE_TWO = "\u041d\u0430\u0431\u043e\u0440 \u043a\u0430\u043d\u0446\u0435\u043b\u044f\u0440\u0438\u0438"
DESCRIPTION_ONE = "\u0411\u0443\u043c\u0430\u0433\u0430 \u0434\u043b\u044f \u043f\u0435\u0447\u0430\u0442\u0438"
DESCRIPTION_TWO = (
    "\u041a\u0430\u043d\u0446\u0442\u043e\u0432\u0430\u0440\u044b "
    "\u0434\u043b\u044f \u043e\u0444\u0438\u0441\u0430"
)
KIT_VALUE = "\u043a\u0430\u043d\u0446\u0442\u043e\u0432\u0430\u0440\u044b"


class StubVectorizer:
    vocabulary_ = {
        "\u043e\u0444\u0438\u0441": 0,
        "\u0431\u0443\u043c\u0430\u0433\u0430": 1,
    }

    def transform(self, texts: list[str]) -> csr_matrix:
        rows = []
        for text in texts:
            lowered = text.lower()
            rows.append(
                [
                    1.0 if "\u0431\u0443\u043c\u0430\u0433\u0430" in lowered else 0.0,
                    1.0 if "\u043a\u0430\u043d\u0446" in lowered else 0.0,
                ]
            )
        return csr_matrix(rows, dtype=float)


class StubModel:
    def __init__(self, predictions: list[float]) -> None:
        self.predictions = np.asarray(predictions, dtype=float)

    def predict(self, matrix: csr_matrix) -> np.ndarray:
        self.last_shape = matrix.shape
        return self.predictions


class StubCatBoostModel:
    def __init__(self, predictions: list[float]) -> None:
        self.predictions = np.asarray(predictions, dtype=float)

    def predict(self, pool: object) -> np.ndarray:
        self.last_pool = pool
        return self.predictions


class StubPool:
    def __init__(
        self,
        *,
        data: list[list[float | str]],
        cat_features: list[int],
        feature_names: list[str],
    ) -> None:
        self.data = data
        self.cat_features = cat_features
        self.feature_names = feature_names


class StubEmbeddingStore:
    vectors = {
        "ste_1": np.asarray([1.0, 0.0], dtype=np.float32),
        "ste_2": np.asarray([0.0, 1.0], dtype=np.float32),
    }

    def get(self, ste_id: str) -> np.ndarray | None:
        return self.vectors.get(ste_id)

    def centroid(self, ste_ids: list[str]) -> np.ndarray | None:
        rows = [self.vectors[ste_id] for ste_id in ste_ids if ste_id in self.vectors]
        if not rows:
            return None
        centroid = np.mean(rows, axis=0, dtype=np.float32)
        norm = float(np.linalg.norm(centroid))
        return centroid if norm == 0 else centroid / norm

    @staticmethod
    def cosine(a: np.ndarray | None, b: np.ndarray | None) -> float:
        if a is None or b is None:
            return 0.0
        return float(np.dot(a, b))

    def max_sim(self, anchor_ids: list[str], candidate_id: str) -> float:
        candidate = self.get(candidate_id)
        if candidate is None:
            return 0.0
        return max(
            (self.cosine(self.get(anchor_id), candidate) for anchor_id in anchor_ids),
            default=0.0,
        )


class LocalMlRankingProviderTests(unittest.TestCase):
    def _make_provider(self) -> LocalMlRankingProvider:
        provider = LocalMlRankingProvider(artifacts_dir=".")
        provider.ready = True
        provider.supports_cyrillic = True
        provider.model_type = "ridge_ranker"
        provider.vectorizer = StubVectorizer()
        provider.model = StubModel([0.1, 0.9])
        provider.numeric_features = [
            "query_len",
            "query_has_digits",
            "is_popular_ste_org",
            "retrieval_score",
            "retrieval_bm25",
            "query_has_synonyms",
            "emb_user_centroid_sim",
            "emb_query_item_sim",
            "emb_max_recent_sim",
        ]
        provider._np = np
        provider._csr_matrix = csr_matrix
        provider._hstack = hstack
        provider.embedding_store = StubEmbeddingStore()
        return provider

    @staticmethod
    def _make_request() -> RankingRequest:
        return RankingRequest(
            query=RankingQueryContext(
                original=QUERY_TEXT,
                normalized=QUERY_TEXT,
                corrected=None,
                applied_synonyms=[QUERY_SYNONYM],
            ),
            actor=CurrentActor(user_id="user_1", organization_id="org_1"),
            profile=SearchProfileRead(
                user_id="user_1",
                organization_id="org_1",
                top_categories=[CATEGORY_NAME],
                org_top_categories=[CATEGORY_NAME],
                recent_ste_ids=["ste_1"],
                top_suppliers=[SUPPLIER_ONE],
                popular_ste_ids=["ste_2"],
                popular_queries=[QUERY_TEXT],
            ),
            candidates=[
                CandidateItem(
                    id="ste_1",
                    title=TITLE_ONE,
                    category=CATEGORY_NAME,
                    supplier=SUPPLIER_ONE,
                    description=DESCRIPTION_ONE,
                    score=0.92,
                    reasons=["partial_title_match", "token_match"],
                    category_id="cat_office",
                    supplier_id="sup_1",
                    status="active",
                    attributes={"format": "A4"},
                    baseline_score=0.92,
                    retrieval_score=0.9,
                    retrieval_reasons=["retrieval_bm25", "retrieval_semantic"],
                    retrieval_channel_scores={"bm25": 0.9},
                ),
                CandidateItem(
                    id="ste_2",
                    title=TITLE_TWO,
                    category=CATEGORY_NAME,
                    supplier=SUPPLIER_TWO,
                    description=DESCRIPTION_TWO,
                    score=0.41,
                    reasons=["token_match"],
                    category_id="cat_office",
                    supplier_id="sup_2",
                    status="active",
                    attributes={"kit": KIT_VALUE},
                    baseline_score=0.41,
                    retrieval_score=0.35,
                    retrieval_reasons=["retrieval_fuzzy"],
                    retrieval_channel_scores={"fuzzy": 0.35},
                ),
            ],
        )

    def test_build_feature_payloads_align_with_training_contract(self) -> None:
        provider = self._make_provider()
        request = self._make_request()

        text_inputs, feature_payloads = provider._build_feature_payloads(request)
        numeric_rows = provider._build_numeric_rows(feature_payloads)

        self.assertIn("cat_office", text_inputs[0])
        self.assertIn("sup_1", text_inputs[0])
        self.assertIn("A4", text_inputs[0])
        self.assertEqual(
            numeric_rows[0],
            [3.0, 1.0, 0.0, 0.9, 1.0, 1.0, 1.0, 1.0, 1.0],
        )
        self.assertEqual(
            numeric_rows[1],
            [3.0, 1.0, 1.0, 0.35, 0.0, 1.0, 0.0, 0.0, 0.0],
        )

    def test_rank_blends_model_with_baseline_and_marks_results(self) -> None:
        provider = self._make_provider()
        request = self._make_request()

        ranked = provider.rank(request)

        self.assertEqual(ranked[0].id, "ste_2")
        self.assertIn("ml_rerank", ranked[0].reasons)
        self.assertEqual(provider.model.last_shape[0], 2)

    def test_rank_falls_back_when_artifact_has_no_cyrillic_support(self) -> None:
        provider = self._make_provider()
        provider.supports_cyrillic = False
        request = self._make_request()

        ranked = provider.rank(request)

        self.assertEqual(ranked[0].id, "ste_1")
        self.assertNotIn("ml_rerank", ranked[0].reasons)

    def test_rank_supports_catboost_artifacts(self) -> None:
        provider = LocalMlRankingProvider(artifacts_dir=".")
        provider.ready = True
        provider.model_type = "catboost_ranker"
        provider.supports_cyrillic = True
        provider.model = StubCatBoostModel([0.2, 0.8])
        provider.feature_columns = [
            "query_len",
            "retrieval_score",
            "item_category_id",
            "item_supplier_id",
        ]
        provider.numeric_features = [
            "query_len",
            "retrieval_score",
        ]
        provider.categorical_features = [
            "item_category_id",
            "item_supplier_id",
        ]
        provider._catboost_pool_cls = StubPool
        provider._np = np

        request = self._make_request()
        ranked = provider.rank(request)

        self.assertEqual(ranked[0].id, "ste_2")
        self.assertIn("ml_rerank", ranked[0].reasons)
        self.assertEqual(provider.model.last_pool.cat_features, [2, 3])
        self.assertEqual(provider.model.last_pool.feature_names, provider.feature_columns)
        self.assertEqual(provider.model.last_pool.data[0][2], "cat_office")
        self.assertEqual(provider.model.last_pool.data[0][3], "sup_1")


if __name__ == "__main__":
    unittest.main()
