import unittest

import numpy as np
from scipy.sparse import csr_matrix, hstack

from app.domain.personalization.schemas import SearchProfileRead
from app.domain.search.schemas import CandidateItem, CurrentActor
from app.integrations.ml.base import RankingQueryContext, RankingRequest
from app.integrations.ml.local import LocalMlRankingProvider


class StubVectorizer:
    vocabulary_ = {"офис": 0, "бумага": 1}

    def transform(self, texts: list[str]) -> csr_matrix:
        rows = []
        for text in texts:
            lowered = text.lower()
            rows.append(
                [
                    1.0 if "бумага" in lowered else 0.0,
                    1.0 if "канц" in lowered else 0.0,
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
            "retrieval_score",
            "retrieval_bm25",
            "title_partial_match",
            "query_has_synonyms",
        ]
        provider._np = np
        provider._csr_matrix = csr_matrix
        provider._hstack = hstack
        return provider

    @staticmethod
    def _make_request() -> RankingRequest:
        return RankingRequest(
            query=RankingQueryContext(
                original="офисная бумага",
                normalized="офисная бумага",
                corrected=None,
                applied_synonyms=["бумага для печати"],
            ),
            actor=CurrentActor(user_id="user_1", organization_id="org_1"),
            profile=SearchProfileRead(
                user_id="user_1",
                organization_id="org_1",
                top_categories=["Офис"],
                org_top_categories=["Офис"],
                recent_ste_ids=["ste_1"],
                top_suppliers=["Поставщик 1"],
                popular_ste_ids=["ste_2"],
                popular_queries=["офисная бумага"],
            ),
            candidates=[
                CandidateItem(
                    id="ste_1",
                    title="Офисная бумага А4",
                    category="Офис",
                    supplier="Поставщик 1",
                    description="Бумага для печати",
                    score=0.92,
                    reasons=["partial_title_match", "token_match"],
                    category_id="cat_office",
                    supplier_id="sup_1",
                    status="active",
                    attributes={"format": "A4"},
                    baseline_score=0.92,
                    retrieval_score=0.9,
                    retrieval_reasons=["retrieval_bm25", "retrieval_semantic"],
                ),
                CandidateItem(
                    id="ste_2",
                    title="Набор канцелярии",
                    category="Офис",
                    supplier="Поставщик 2",
                    description="Канцтовары для офиса",
                    score=0.41,
                    reasons=["token_match"],
                    category_id="cat_office",
                    supplier_id="sup_2",
                    status="active",
                    attributes={"kit": "канцтовары"},
                    baseline_score=0.41,
                    retrieval_score=0.35,
                    retrieval_reasons=["retrieval_fuzzy"],
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
        self.assertEqual(numeric_rows[0], [2.0, 0.9, 1.0, 1.0, 1.0])
        self.assertEqual(numeric_rows[1], [2.0, 0.35, 0.0, 0.0, 1.0])

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
