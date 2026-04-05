import unittest
from unittest.mock import MagicMock, patch

from app.domain.search.normalizer import (
    FuzzyQueryCorrection,
    FuzzyTokenCorrection,
    build_spell_vocabulary_index,
)
from app.domain.search.service import SearchService


class SearchServiceQueryResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog_service = MagicMock()
        self.event_service = MagicMock()
        self.personalization_service = MagicMock()
        self.search_repository = MagicMock()
        self.ranking_provider = MagicMock()
        self.service = SearchService(
            catalog_service=self.catalog_service,
            event_service=self.event_service,
            personalization_service=self.personalization_service,
            search_repository=self.search_repository,
            ranking_provider=self.ranking_provider,
        )

    def test_resolve_query_uses_high_confidence_fuzzy_correction_as_primary(self) -> None:
        self.search_repository.get_search_spell_vocabulary.return_value = build_spell_vocabulary_index(
            {"принтер", "принтеры", "картридж"},
            token_frequencies={"принтер": 10, "принтеры": 4},
            protected_tokens={"hp", "12a"},
        )
        self.search_repository.get_spell_corrections.return_value = {}

        resolved = self.service._resolve_query("принтэр hp 12a")

        self.assertEqual(resolved.effective_query, "принтер hp 12a")
        self.assertEqual(resolved.corrected_query, "принтер hp 12a")
        self.assertEqual(resolved.correction_type, "fuzzy_spellcheck")
        self.assertEqual(resolved.correction_confidence, "high")
        self.assertIn("принтэр hp 12a", resolved.active_queries)
        self.assertIn("принтер hp 12a", resolved.active_queries)

    def test_medium_confidence_correction_is_kept_as_search_variant_not_primary(self) -> None:
        self.search_repository.get_search_spell_vocabulary.return_value = build_spell_vocabulary_index(
            {"принтер"}
        )
        self.search_repository.get_spell_corrections.return_value = {}

        with patch(
            "app.domain.search.service.resolve_query_fuzzy_correction",
            return_value=FuzzyQueryCorrection(
                corrected_query="принтер",
                confidence="medium",
                confidence_score=0.71,
                token_corrections=(
                    FuzzyTokenCorrection(
                        source="принтэр",
                        corrected="принтер",
                        confidence="medium",
                        confidence_score=0.71,
                    ),
                ),
            ),
        ):
            resolved = self.service._resolve_query("принтэр")

        self.assertEqual(resolved.effective_query, "принтэр")
        self.assertIsNone(resolved.corrected_query)
        self.assertEqual(resolved.correction_type, "none")
        self.assertEqual(set(resolved.active_queries), {"принтэр", "принтер"})


if __name__ == "__main__":
    unittest.main()
