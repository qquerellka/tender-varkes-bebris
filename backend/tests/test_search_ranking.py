import unittest

from app.domain.catalog.schemas import STEItemRead
from app.domain.personalization.schemas import SearchProfileRead
from app.domain.search.ranking import build_candidate


class SearchRankingTests(unittest.TestCase):
    def test_retrieval_score_contributes_to_candidate_score(self) -> None:
        item = STEItemRead(
            id="ste_1",
            title="Поставка офисной бумаги",
            description="Бумага для печати",
            category_id="cat_1",
            category_name="Офис",
            supplier_id="sup_1",
            supplier_name="Поставщик",
            attributes={"format": "a4"},
            status="active",
        )
        profile = SearchProfileRead(user_id="user_1", organization_id="org_1")

        candidate = build_candidate(
            item=item,
            normalized_query="бумага",
            profile=profile,
            query_terms=["бумага"],
            retrieval_score=0.8,
            retrieval_reasons=[
                "retrieval_exact",
                "retrieval_bm25",
                "retrieval_fuzzy",
                "retrieval_semantic",
            ],
            retrieval_channel_scores={
                "exact_structured": 0.92,
                "bm25": 0.88,
            },
            retrieval_channel_ranks={
                "exact_structured": 1,
                "bm25": 2,
            },
            retrieval_features={
                "attribute_overlap_count": 2.0,
                "brand_match_flag": 1.0,
                "numeric_constraint_match_flag": 1.0,
            },
        )

        self.assertGreater(candidate.score, 0.6)
        self.assertEqual(candidate.baseline_score, candidate.score)
        self.assertEqual(candidate.retrieval_score, 0.8)
        self.assertEqual(candidate.category_id, "cat_1")
        self.assertEqual(candidate.supplier_id, "sup_1")
        self.assertEqual(candidate.status, "active")
        self.assertEqual(candidate.attributes, {"format": "a4"})
        self.assertEqual(candidate.retrieval_channel_scores["exact_structured"], 0.92)
        self.assertEqual(candidate.retrieval_channel_ranks["bm25"], 2)
        self.assertEqual(candidate.retrieval_features["brand_match_flag"], 1.0)
        self.assertEqual(
            candidate.retrieval_reasons,
            [
                "retrieval_exact",
                "retrieval_bm25",
                "retrieval_fuzzy",
                "retrieval_semantic",
            ],
        )
        self.assertIn("brand_match", candidate.reasons)
        self.assertIn("numeric_constraint_match", candidate.reasons)
        self.assertIn("retrieval_bm25", candidate.reasons)
        self.assertIn("retrieval_fuzzy", candidate.reasons)
        self.assertIn("retrieval_semantic", candidate.reasons)


if __name__ == "__main__":
    unittest.main()
