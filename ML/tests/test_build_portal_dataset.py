from __future__ import annotations

import csv
import re
import shutil
import sys
import types
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT_DIR / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

TOKEN_RE = re.compile(r"[0-9a-zа-яё]+", flags=re.IGNORECASE)


def _normalize_query(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("ё", "е").split())


def _extract_query_terms(value: str) -> list[str]:
    return TOKEN_RE.findall(_normalize_query(value))


class _FakeRetrievalResult:
    def __init__(self, document_id: str) -> None:
        self.document_id = document_id


class _FakeRetrievalFeatureBuilder:
    def __init__(
        self,
        *,
        item_by_id: dict[str, dict[str, str]],
        category_by_id: dict[str, dict[str, str]],
        supplier_by_id: dict[str, dict[str, str]],
        synonym_rows: list[dict[str, str]],
        spell_rows: list[dict[str, str]],
    ) -> None:
        self.item_by_id = item_by_id

    def search(
        self,
        *,
        query: str,
        normalized_query: str,
        limit: int = 80,
        strict_match: bool = False,
        candidate_item_ids: set[str] | None = None,
    ) -> tuple[object, list[_FakeRetrievalResult]]:
        query_terms = set(_extract_query_terms(normalized_query or query))
        source_items = (
            list(self.item_by_id.values())
            if candidate_item_ids is None
            else [
                item
                for item_id, item in self.item_by_id.items()
                if item_id in candidate_item_ids
            ]
        )
        ranked = sorted(
            source_items,
            key=lambda item: (
                len(query_terms & set(_extract_query_terms(item["title"]))),
                item["title"],
            ),
            reverse=True,
        )
        return object(), [_FakeRetrievalResult(item["id"]) for item in ranked[:limit]]


fake_retrieval = types.ModuleType("retrieval_feature_enrichment")
fake_retrieval.RetrievalFeatureBuilder = _FakeRetrievalFeatureBuilder
sys.modules.setdefault("retrieval_feature_enrichment", fake_retrieval)

app_module = sys.modules.setdefault("app", types.ModuleType("app"))
domain_module = sys.modules.setdefault("app.domain", types.ModuleType("app.domain"))
search_module = sys.modules.setdefault("app.domain.search", types.ModuleType("app.domain.search"))
normalizer_module = types.ModuleType("app.domain.search.normalizer")
normalizer_module.normalize_query = _normalize_query
normalizer_module.extract_query_terms = _extract_query_terms
sys.modules.setdefault("app.domain.search.normalizer", normalizer_module)
setattr(app_module, "domain", domain_module)
setattr(domain_module, "search", search_module)
setattr(search_module, "normalizer", normalizer_module)

import build_portal_dataset as portal_builder


class BuildPortalDatasetTests(unittest.TestCase):
    def _write_rows(self, path: Path, rows: list[list[str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerows(rows)

    def test_builds_compact_training_rows_from_small_portal_fixtures(self) -> None:
        root = ROOT_DIR / ".tmp-test-fixtures" / "build_portal_dataset"
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        try:
            ste_path = root / "orig" / "ste_source" / "ste.csv"
            contracts_path = root / "orig" / "contracts_source" / "contracts.csv"

            self._write_rows(
                ste_path,
                [
                    [
                        "1001",
                        "Автобус школьный дизельный 32 места",
                        "Автобусы пассажирские",
                        "Производитель:ООО Транспорт;Мест:32;Тип:дизельный",
                    ],
                    [
                        "1002",
                        "Автобус туристический 40 мест",
                        "Автобусы пассажирские",
                        "Производитель:ООО Тур Транс;Мест:40;Тип:туристический",
                    ],
                    [
                        "1003",
                        "Флеш накопитель USB 16 ГБ",
                        "Usb-накопители",
                        "Производитель:SMARTBUY;Объем:16;Интерфейс:USB 2",
                    ],
                ],
            )
            self._write_rows(
                contracts_path,
                [
                    [
                        "Автобус школьный дизельный 32 места",
                        "contract-1",
                        "ext-1",
                        "2026-01-02 10:00:00.000",
                        "1200000.00",
                        "7700000001",
                        "Департамент транспорта",
                        "Москва",
                        "7700001000",
                        "ООО Транспорт",
                        "Москва",
                    ]
                ],
            )

            (
                item_by_id,
                category_by_id,
                supplier_by_id,
                token_to_category_ids,
                category_samples,
                _catalog_stats,
            ) = portal_builder._build_sampled_catalog(
                ste_csv_path=ste_path,
                max_samples_per_category=8,
            )
            self.assertGreaterEqual(len(item_by_id), 3)

            retrieval_builder = portal_builder.RetrievalFeatureBuilder(
                item_by_id=item_by_id,
                category_by_id=category_by_id,
                supplier_by_id=supplier_by_id,
                synonym_rows=portal_builder._build_default_synonym_rows(),
                spell_rows=portal_builder._build_default_spell_rows(),
            )
            dataset_rows, dataset_stats = portal_builder._build_dataset_rows(
                contracts_csv_path=contracts_path,
                item_by_id=item_by_id,
                token_to_category_ids=token_to_category_ids,
                category_samples=category_samples,
                retrieval_builder=retrieval_builder,
                config=portal_builder.BuildConfig(
                    contract_limit=0,
                    max_organizations=4,
                    max_contracts_per_org=4,
                    candidate_limit=3,
                    visible_limit=3,
                    query_term_limit=6,
                    min_query_terms=1,
                    min_match_score=1.0,
                    max_samples_per_category=8,
                ),
            )

            self.assertEqual(dataset_stats["sessions_created"], 1)
            self.assertEqual(len(dataset_rows["query_relevance"]), 3)
            self.assertTrue(any(row["label"] == "3" for row in dataset_rows["query_relevance"]))
        finally:
            if root.exists():
                shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
