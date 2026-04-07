import unittest

from app.domain.search.query_analysis import analyze_search_text


class QueryAnalysisTests(unittest.TestCase):
    def test_analysis_extracts_brand_model_size_and_quantity(self) -> None:
        analysis = analyze_search_text("картридж hp 12a 2 шт")

        self.assertIn("hp", analysis.brand_terms)
        self.assertIn("12a", analysis.model_terms)
        self.assertIn("штука", analysis.unit_terms)
        self.assertEqual(analysis.quantity_constraints[0].normalized, "2 штука")
        self.assertIn("картридж", analysis.category_hints)

    def test_analysis_extracts_format_color_and_packaging(self) -> None:
        analysis = analyze_search_text("бумага a4 белая 500 листов")

        self.assertIn("a4", analysis.size_terms)
        self.assertIn("белый", analysis.color_terms)
        self.assertIn("лист", analysis.unit_terms)
        self.assertEqual(analysis.quantity_constraints[0].normalized, "500 лист")
        self.assertIn("бумага", analysis.category_hints)

    def test_analysis_extracts_material_and_glove_size(self) -> None:
        analysis = analyze_search_text("перчатки нитриловые черные l")

        self.assertIn("нитриловый", analysis.material_terms)
        self.assertIn("черный", analysis.color_terms)
        self.assertIn("l", analysis.size_terms)
        self.assertIn("перчатки", analysis.category_hints)


if __name__ == "__main__":
    unittest.main()
