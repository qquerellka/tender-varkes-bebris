from datetime import datetime
import unittest
from unittest.mock import patch

import numpy as np

from app.domain.search.normalizer import lemmatize_query_terms
from app.domain.search.query_analysis import analyze_search_text
from app.domain.search.retrieval import HybridSearchIndex, SearchDocument


def _fake_bge_embeddings(texts: list[str]) -> np.ndarray:
    vectors: list[list[float]] = []
    for text in texts:
        normalized = text.lower()
        if "кресл" in normalized or "оператор" in normalized:
            vectors.append([1.0, 0.0, 0.0])
        elif "бумаг" in normalized or "принтер" in normalized:
            vectors.append([0.0, 1.0, 0.0])
        elif "картридж" in normalized or "hp" in normalized:
            vectors.append([0.0, 0.0, 1.0])
        else:
            vectors.append([0.0, 0.0, 0.5])
    return np.asarray(vectors, dtype=np.float32)


class HybridRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.index = HybridSearchIndex(
            [
                SearchDocument(
                    id="ste_paper",
                    title="Бумага офисная A4 500 листов",
                    description="Бумага для принтера, канцелярские товары и ежедневная офисная печать",
                    category_id="cat_office",
                    category_name="Офис и снабжение",
                    supplier_id="sup_1",
                    supplier_name="Поставщик офиса",
                    attributes={"format": "A4", "pack": "500 листов", "color": "белая"},
                    updated_at=datetime(2026, 3, 29),
                ),
                SearchDocument(
                    id="ste_cartridge",
                    title="Картридж HP 12A лазерный",
                    description="Оригинальный картридж для офисной печати",
                    category_id="cat_office",
                    category_name="Офис и снабжение",
                    supplier_id="sup_2",
                    supplier_name="Поставщик печати",
                    attributes={"brand": "HP", "model": "12A", "pack": "2 штука"},
                    updated_at=datetime(2026, 3, 29),
                ),
                SearchDocument(
                    id="ste_printer",
                    title="Поставка лазерных принтеров",
                    description="Оргтехника для офисной печати",
                    category_id="cat_it",
                    category_name="ИТ и оборудование",
                    supplier_id="sup_3",
                    supplier_name="Поставщик техники",
                    attributes={"type": "printer"},
                    updated_at=datetime(2026, 3, 29),
                ),
                SearchDocument(
                    id="ste_server",
                    title="Поставка серверного оборудования",
                    description="Серверы и вычислительные узлы для дата центра",
                    category_id="cat_it",
                    category_name="ИТ и оборудование",
                    supplier_id="sup_4",
                    supplier_name="Инфра поставщик",
                    attributes={"type": "server"},
                    updated_at=datetime(2026, 3, 29),
                ),
            ]
        )

    def _search(
        self,
        query: str,
        *,
        synonym_terms: list[str] | None = None,
        semantic_texts: list[str] | None = None,
    ):
        analysis = analyze_search_text(query)
        return self.index.search(
            lexical_terms=[query],
            morphology_terms=lemmatize_query_terms(analysis.text_terms),
            synonym_terms=synonym_terms or [],
            trigram_terms=[query],
            semantic_texts=semantic_texts or [query],
            structured_query=analysis,
            strict_match=False,
        )

    def test_exact_structured_recalls_brand_model_and_quantity(self) -> None:
        results = self._search("картридж hp 12a 2 шт")

        self.assertEqual(results[0].document_id, "ste_cartridge")
        self.assertIn("retrieval_exact", results[0].reasons)
        self.assertEqual(results[0].features["brand_match_flag"], 1.0)
        self.assertEqual(results[0].features["numeric_constraint_match_flag"], 1.0)

    def test_attribute_channel_recalls_format_and_packaging(self) -> None:
        results = self._search("бумага a4 500 листов")

        self.assertEqual(results[0].document_id, "ste_paper")
        self.assertIn("retrieval_attribute", results[0].reasons)
        self.assertGreaterEqual(results[0].features["attribute_overlap_count"], 2.0)

    def test_synonym_bm25_recalls_stationery(self) -> None:
        results = self._search(
            "канцелярия",
            synonym_terms=["канцтовары", "канцелярские товары"],
            semantic_texts=["канцелярия", "канцтовары"],
        )

        self.assertEqual(results[0].document_id, "ste_paper")
        self.assertIn("retrieval_synonym", results[0].reasons)

    def test_fuzzy_channel_recalls_typo(self) -> None:
        results = self._search("принтэр")

        self.assertEqual(results[0].document_id, "ste_printer")
        self.assertIn("retrieval_fuzzy", results[0].reasons)
        self.assertGreater(results[0].features["fuzzy_edit_score"], 0.5)

    def test_rrf_marks_multi_channel_hits(self) -> None:
        results = self._search("серверное оборудование")

        self.assertEqual(results[0].document_id, "ste_server")
        self.assertIn("retrieval_bm25", results[0].reasons)
        self.assertIn("retrieval_semantic", results[0].reasons)
        self.assertIn("retrieval_rrf", results[0].reasons)
        self.assertEqual(results[0].features["appeared_in_multiple_channels"], 1.0)

    def test_build_time_state_is_released_after_index_construction(self) -> None:
        document = self.index.documents[0]

        self.assertIsNone(document.field_terms)
        self.assertIsNone(document.field_lemma_terms)
        self.assertIsNone(document.analysis_by_field)
        self.assertEqual(set(document.field_texts), {"title", "attributes", "description"})
        self.assertEqual(set(document.field_term_sets), {"title", "category", "attributes"})
        self.assertEqual(set(document.field_lemma_sets), {"title", "category"})

    @patch("app.domain.search.retrieval.build_faiss_index", return_value=None)
    @patch(
        "app.domain.search.retrieval.encode_bge_m3_texts",
        side_effect=_fake_bge_embeddings,
    )
    def test_bge_m3_backend_is_used_when_dense_embeddings_are_available(
        self,
        _encode_mock,
        _faiss_mock,
    ) -> None:
        index = HybridSearchIndex(
            [
                SearchDocument(
                    id="ste_chair",
                    title="Эргономичное кресло оператора",
                    description="Регулируемое кресло для рабочего места",
                    category_id="cat_furniture",
                    category_name="Офисная мебель",
                    supplier_id="sup_5",
                    supplier_name="Поставщик мебели",
                    attributes={"type": "chair"},
                    updated_at=datetime(2026, 3, 29),
                ),
                SearchDocument(
                    id="ste_printer",
                    title="Лазерный принтер для офиса",
                    description="Оргтехника для печати",
                    category_id="cat_it",
                    category_name="ИТ и оборудование",
                    supplier_id="sup_6",
                    supplier_name="Поставщик техники",
                    attributes={"type": "printer"},
                    updated_at=datetime(2026, 3, 29),
                ),
            ]
        )

        analysis = analyze_search_text("кресло для офиса")
        results = index.search(
            lexical_terms=["кресло для офиса"],
            morphology_terms=lemmatize_query_terms(analysis.text_terms),
            synonym_terms=[],
            trigram_terms=["кресло для офиса"],
            semantic_texts=["кресло для офиса"],
            structured_query=analysis,
            strict_match=False,
        )

        self.assertEqual(index._semantic_backend, "bge_m3")
        self.assertEqual(results[0].document_id, "ste_chair")
        self.assertEqual(results[0].features["semantic_backend_bge_m3"], 1.0)
        self.assertEqual(results[0].features["semantic_backend_fallback"], 0.0)


if __name__ == "__main__":
    unittest.main()
