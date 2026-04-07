import unittest

from app.db.portal_csv_loader import _normalize_space, _parse_attributes


class PortalCsvLoaderTests(unittest.TestCase):
    def test_normalize_space_removes_nul_bytes(self) -> None:
        self.assertEqual(_normalize_space("ab\x00c \x00 def"), "abc def")

    def test_parse_attributes_removes_nul_bytes_from_keys_and_values(self) -> None:
        attributes = _parse_attributes("Бре\x00нд:SMA\x00RTBUY; Цвет: чер\x00ный")

        self.assertEqual(
            attributes,
            {
                "Бренд": "SMARTBUY",
                "Цвет": "черный",
            },
        )


if __name__ == "__main__":
    unittest.main()
