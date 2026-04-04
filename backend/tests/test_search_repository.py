from datetime import datetime
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.db.repositories.search import SearchRepository
from app.domain.search.retrieval import HybridSearchIndex, SearchDocument


def _sample_document() -> SearchDocument:
    return SearchDocument(
        id="ste_1",
        title="Office chair",
        description="Ergonomic chair for workplace",
        category_id="cat_1",
        category_name="Furniture",
        supplier_id="sup_1",
        supplier_name="Supplier",
        attributes={"color": "black"},
        updated_at=datetime(2026, 4, 4, 12, 0, 0),
    )


class SearchRepositoryCacheTests(unittest.TestCase):
    def test_persisted_hybrid_index_round_trip(self) -> None:
        document = _sample_document()
        signature = (1, document.updated_at)
        index = HybridSearchIndex([document], enable_semantic=False)

        with TemporaryDirectory() as tmpdir, patch(
            "app.db.repositories.search.settings.search_index_cache_path",
            f"{tmpdir}/hybrid_search_index.pkl",
        ), patch(
            "app.db.repositories.search.settings.search_semantic_backend",
            "disabled",
        ):
            SearchRepository._save_persisted_hybrid_index(signature, index)
            loaded_index = SearchRepository._load_persisted_hybrid_index(signature)

        self.assertIsNotNone(loaded_index)
        assert loaded_index is not None
        self.assertEqual(len(loaded_index.documents), 1)
        self.assertEqual(loaded_index.documents[0].payload.id, document.id)
        self.assertEqual(loaded_index._semantic_backend, "disabled")

    def test_persisted_hybrid_index_invalidates_when_semantic_mode_changes(self) -> None:
        document = _sample_document()
        signature = (1, document.updated_at)
        index = HybridSearchIndex([document], enable_semantic=False)

        with TemporaryDirectory() as tmpdir, patch(
            "app.db.repositories.search.settings.search_index_cache_path",
            f"{tmpdir}/hybrid_search_index.pkl",
        ), patch(
            "app.db.repositories.search.settings.search_semantic_backend",
            "disabled",
        ):
            SearchRepository._save_persisted_hybrid_index(signature, index)

            with patch(
                "app.db.repositories.search.settings.search_semantic_backend",
                "auto",
            ):
                loaded_index = SearchRepository._load_persisted_hybrid_index(signature)

        self.assertIsNone(loaded_index)


class HybridSearchIndexSettingsTests(unittest.TestCase):
    def test_settings_can_disable_semantic_backend_globally(self) -> None:
        with patch(
            "app.domain.search.retrieval.settings.search_semantic_backend",
            "disabled",
        ):
            index = HybridSearchIndex([_sample_document()])

        self.assertEqual(index._semantic_backend, "disabled")
        self.assertIsNone(index._semantic_faiss_index)


if __name__ == "__main__":
    unittest.main()
