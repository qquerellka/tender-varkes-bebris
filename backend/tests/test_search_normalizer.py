import unittest

from app.domain.search.normalizer import (
    build_spell_vocabulary_index,
    correct_keyboard_layout,
    correct_query_fuzzy,
    expand_fuzzy_term_variants,
    expand_term_variants,
    extract_query_terms,
    normalize_query,
    resolve_query_fuzzy_correction,
)


class SearchNormalizerTests(unittest.TestCase):
    def test_normalize_query_compacts_common_phrases(self) -> None:
        self.assertEqual(
            normalize_query("  Канц товары, для офиса  "),
            "канцтовары для офиса",
        )

    def test_keyboard_layout_correction_is_conservative_for_latin_terms(self) -> None:
        self.assertIsNone(correct_keyboard_layout("noutbuk"))
        self.assertEqual(correct_keyboard_layout("ghbynth"), "принтер")

    def test_extract_query_terms_normalizes_units(self) -> None:
        self.assertEqual(
            extract_query_terms("бумага а4 80 г/м2 10 шт"),
            ["бумага", "а4", "80", "грамм на квадратный метр", "10", "штука"],
        )

    def test_fuzzy_spellcheck_fixes_live_typos(self) -> None:
        vocabulary = {"автобус", "принтер", "канцелярия", "канцтовары"}

        self.assertEqual(correct_query_fuzzy("принтэр", vocabulary), "принтер")
        self.assertEqual(correct_query_fuzzy("афтобус", vocabulary), "автобус")

    def test_fuzzy_spellcheck_returns_confidence_for_clear_winner(self) -> None:
        vocabulary = build_spell_vocabulary_index(
            {"принтер", "принтеры", "картридж"},
            token_frequencies={"принтер": 12, "принтеры": 4},
        )

        correction = resolve_query_fuzzy_correction("принтэр", vocabulary)

        self.assertIsNotNone(correction)
        assert correction is not None
        self.assertEqual(correction.corrected_query, "принтер")
        self.assertEqual(correction.confidence, "high")

    def test_fuzzy_spellcheck_does_not_touch_protected_brand_model_tokens(self) -> None:
        vocabulary = build_spell_vocabulary_index(
            {"принтер", "картридж", "usb", "ssd"},
            protected_tokens={"hp", "12a", "usb", "ssd", "a4"},
        )

        self.assertIsNone(
            correct_query_fuzzy(
                "hp 12a usb ssd a4",
                vocabulary,
                protected_tokens={"hp", "12a", "usb", "ssd", "a4"},
            )
        )

    def test_expand_term_variants_adds_domain_aliases_and_morphology(self) -> None:
        variants = expand_term_variants(
            ["мфу", "услуги", "офисные", "принтеры", "канцелярия"]
        )

        self.assertIn("многофункциональное устройство", variants)
        self.assertIn("принтер", variants)
        self.assertIn("услуга", variants)
        self.assertIn("офисный", variants)
        self.assertIn("канцтовары", variants)
        self.assertIn("канцелярские товары", variants)

    def test_expand_fuzzy_term_variants_builds_retrieval_candidates(self) -> None:
        vocabulary = {
            "автобус",
            "принтер",
            "принтеры",
            "канцелярия",
            "канцтовары",
        }

        variants = expand_fuzzy_term_variants(
            ["принтэр", "афтобус"],
            vocabulary,
        )

        self.assertIn("принтер", variants)
        self.assertIn("автобус", variants)


if __name__ == "__main__":
    unittest.main()
