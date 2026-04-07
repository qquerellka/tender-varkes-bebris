from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent
for candidate in (ROOT_DIR, TOOLS_DIR):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

try:
    from retrieval_feature_enrichment import RetrievalFeatureBuilder, SessionRetrievalFeatures
except ImportError:
    from .retrieval_feature_enrichment import (  # type: ignore[no-redef]
        RetrievalFeatureBuilder,
        SessionRetrievalFeatures,
    )


ISO_FRACTION_RE = re.compile(
    r"^(?P<prefix>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d+))?"
    r"(?P<suffix>Z|[+-]\d{2}:\d{2})?$"
)


@dataclass(frozen=True)
class SplitConfig:
    train_ratio: float
    val_ratio: float
    test_ratio: float

    def validate(self) -> None:
        total = self.train_ratio + self.val_ratio + self.test_ratio
        if abs(total - 1.0) > 1e-8:
            raise ValueError("Split ratios must sum to 1.0")
        if min(self.train_ratio, self.val_ratio, self.test_ratio) <= 0:
            raise ValueError("All split ratios must be greater than 0")


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_source = script_dir.parent / "data" / "orig" / "derived"
    default_output = default_source / "splits"

    parser = argparse.ArgumentParser(
        description="Build time-based train/val/test ranking datasets from orig-derived CSV."
    )
    parser.add_argument("--source-dir", type=Path, default=default_source)
    parser.add_argument("--output-dir", type=Path, default=default_output)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    return parser.parse_args()


def parse_iso_datetime(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"

    match = ISO_FRACTION_RE.match(value)
    if match and match.group("fraction"):
        fraction = match.group("fraction")[:6]
        suffix = match.group("suffix") or ""
        value = f"{match.group('prefix')}.{fraction}{suffix}"

    return datetime.fromisoformat(value)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def load_index(path: Path, key: str) -> dict[str, dict[str, str]]:
    return {row[key]: row for row in load_csv(path)}


def log_step(message: str) -> None:
    print(f"[build_ml_splits] {message}", flush=True)


def format_seconds(value: float) -> str:
    total_seconds = max(int(value), 0)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def build_session_split_map(
    relevance_rows: list[dict[str, str]],
    config: SplitConfig,
) -> dict[str, str]:
    first_seen: dict[str, datetime] = {}
    for row in relevance_rows:
        session_id = row["session_id"]
        created_at = parse_iso_datetime(row["created_at"])
        if session_id not in first_seen or created_at < first_seen[session_id]:
            first_seen[session_id] = created_at

    ordered_sessions = sorted(first_seen.items(), key=lambda item: item[1])
    total = len(ordered_sessions)
    train_cut = int(total * config.train_ratio)
    val_cut = int(total * (config.train_ratio + config.val_ratio))

    mapping: dict[str, str] = {}
    for idx, (session_id, _) in enumerate(ordered_sessions):
        if idx < train_cut:
            mapping[session_id] = "train"
        elif idx < val_cut:
            mapping[session_id] = "val"
        else:
            mapping[session_id] = "test"
    return mapping


def enrich_row(
    row: dict[str, str],
    item_by_id: dict[str, dict[str, str]],
    category_by_id: dict[str, dict[str, str]],
    supplier_by_id: dict[str, dict[str, str]],
    user_profile_by_user_id: dict[str, dict[str, str]],
    org_profile_by_org_id: dict[str, dict[str, str]],
    retrieval_features: SessionRetrievalFeatures | None = None,
) -> dict[str, Any]:
    item = item_by_id.get(row["ste_id"], {})
    category = category_by_id.get(item.get("category_id", ""), {})
    supplier = supplier_by_id.get(item.get("supplier_id", ""), {})
    user_profile = user_profile_by_user_id.get(row["user_id"], {})
    org_profile = org_profile_by_org_id.get(row["organization_id"], {})
    retrieval_row = {}
    if retrieval_features is not None:
        retrieval_row = retrieval_features.features_by_item_id.get(row["ste_id"], {})

    return {
        "session_id": row["session_id"],
        "group_id": row["session_id"],
        "user_id": row["user_id"],
        "organization_id": row["organization_id"],
        "query": row["query"],
        "normalized_query": row["normalized_query"],
        "ste_id": row["ste_id"],
        "position": row["position"],
        "label": row["label"],
        "clicked": row["clicked"],
        "purchased": row["purchased"],
        "viewed": row["viewed"],
        "created_at": row["created_at"],
        "item_title": item.get("title", ""),
        "item_description": item.get("description", ""),
        "item_category_id": item.get("category_id", ""),
        "item_category_name": category.get("name", ""),
        "item_supplier_id": item.get("supplier_id", ""),
        "item_supplier_name": supplier.get("name", ""),
        "item_status": item.get("status", ""),
        "item_attributes_json": item.get("attributes_json", "{}"),
        "user_top_categories_json": user_profile.get("top_categories_json", "[]"),
        "user_recent_ste_ids_json": user_profile.get("recent_ste_ids_json", "[]"),
        "user_top_suppliers_json": user_profile.get("top_suppliers_json", "[]"),
        "user_popular_queries_json": user_profile.get("popular_queries_json", "[]"),
        "org_top_categories_json": org_profile.get("top_categories_json", "[]"),
        "org_popular_ste_ids_json": org_profile.get("popular_ste_ids_json", "[]"),
        "query_has_correction": (
            retrieval_features.query_has_correction if retrieval_features is not None else 0.0
        ),
        "query_has_synonyms": (
            retrieval_features.query_has_synonyms if retrieval_features is not None else 0.0
        ),
        "retrieval_score": float(retrieval_row.get("retrieval_score", 0.0)),
        "retrieval_channel_count": float(retrieval_row.get("retrieval_channel_count", 0.0)),
        "retrieval_exact": float(retrieval_row.get("retrieval_exact", 0.0)),
        "retrieval_attribute": float(retrieval_row.get("retrieval_attribute", 0.0)),
        "retrieval_bm25": float(retrieval_row.get("retrieval_bm25", 0.0)),
        "retrieval_morphology": float(retrieval_row.get("retrieval_morphology", 0.0)),
        "retrieval_fuzzy": float(retrieval_row.get("retrieval_fuzzy", 0.0)),
        "retrieval_synonym": float(retrieval_row.get("retrieval_synonym", 0.0)),
        "retrieval_rrf": float(retrieval_row.get("retrieval_rrf", 0.0)),
        "channel_score_exact_structured": float(
            retrieval_row.get("channel_score_exact_structured", 0.0)
        ),
        "channel_score_attribute": float(retrieval_row.get("channel_score_attribute", 0.0)),
        "channel_score_bm25": float(retrieval_row.get("channel_score_bm25", 0.0)),
        "channel_score_morphology": float(retrieval_row.get("channel_score_morphology", 0.0)),
        "channel_score_fuzzy": float(retrieval_row.get("channel_score_fuzzy", 0.0)),
        "channel_score_synonym_bm25": float(
            retrieval_row.get("channel_score_synonym_bm25", 0.0)
        ),
        "channel_rank_exact_structured": float(
            retrieval_row.get("channel_rank_exact_structured", 0.0)
        ),
        "channel_rank_attribute": float(retrieval_row.get("channel_rank_attribute", 0.0)),
        "channel_rank_bm25": float(retrieval_row.get("channel_rank_bm25", 0.0)),
        "channel_rank_morphology": float(retrieval_row.get("channel_rank_morphology", 0.0)),
        "channel_rank_fuzzy": float(retrieval_row.get("channel_rank_fuzzy", 0.0)),
        "channel_rank_synonym_bm25": float(
            retrieval_row.get("channel_rank_synonym_bm25", 0.0)
        ),
        "exact_match_flag": float(retrieval_row.get("exact_match_flag", 0.0)),
        "phrase_match_flag": float(retrieval_row.get("phrase_match_flag", 0.0)),
        "category_match_flag": float(retrieval_row.get("category_match_flag", 0.0)),
        "brand_match_flag": float(retrieval_row.get("brand_match_flag", 0.0)),
        "numeric_constraint_match_flag": float(
            retrieval_row.get("numeric_constraint_match_flag", 0.0)
        ),
        "attribute_overlap_count": float(retrieval_row.get("attribute_overlap_count", 0.0)),
        "appeared_in_multiple_channels": float(
            retrieval_row.get("appeared_in_multiple_channels", 0.0)
        ),
        "strict_term_coverage": float(retrieval_row.get("strict_term_coverage", 0.0)),
        "fuzzy_edit_score": float(retrieval_row.get("fuzzy_edit_score", 0.0)),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows to write for {path}")

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    started_at = time.perf_counter()

    config = SplitConfig(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
    )
    config.validate()

    log_step(f"Loading source CSV files from {source_dir}")
    relevance_rows = load_csv(source_dir / "query_relevance.csv")
    item_by_id = load_index(source_dir / "ste_items.csv", key="id")
    category_by_id = load_index(source_dir / "categories.csv", key="id")
    supplier_by_id = load_index(source_dir / "suppliers.csv", key="id")
    user_profile_by_user_id = load_index(source_dir / "user_search_profiles.csv", key="user_id")
    org_profile_by_org_id = load_index(source_dir / "org_search_profiles.csv", key="organization_id")
    synonym_rows = load_csv(source_dir / "synonyms.csv")
    spell_rows = load_csv(source_dir / "spell_corrections.csv")
    log_step(
        "Loaded "
        f"{len(relevance_rows)} relevance rows, "
        f"{len(item_by_id)} items, "
        f"{len(category_by_id)} categories, "
        f"{len(supplier_by_id)} suppliers"
    )

    log_step("Building retrieval feature index")
    retrieval_builder = RetrievalFeatureBuilder(
        item_by_id=item_by_id,
        category_by_id=category_by_id,
        supplier_by_id=supplier_by_id,
        synonym_rows=synonym_rows,
        spell_rows=spell_rows,
        progress=True,
    )
    log_step(f"Search index ready with {len(retrieval_builder.documents)} documents")

    session_queries: dict[str, tuple[str, str]] = {}
    session_candidate_ids: dict[str, set[str]] = {}
    for row in relevance_rows:
        session_queries.setdefault(
            row["session_id"],
            (row.get("query", ""), row.get("normalized_query", "")),
        )
        session_candidate_ids.setdefault(row["session_id"], set()).add(row["ste_id"])
    log_step(f"Computing retrieval features for {len(session_queries)} sessions")
    session_retrieval_features = retrieval_builder.build_session_feature_map(
        session_queries,
        candidate_item_ids_by_session=session_candidate_ids,
        progress_every=max(100, len(session_queries) // 20),
    )

    log_step("Assigning sessions to train/val/test")
    session_split = build_session_split_map(relevance_rows, config=config)

    split_rows: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    total_rows = len(relevance_rows)
    for index, row in enumerate(relevance_rows, start=1):
        split_name = session_split[row["session_id"]]
        split_rows[split_name].append(
            enrich_row(
                row=row,
                item_by_id=item_by_id,
                category_by_id=category_by_id,
                supplier_by_id=supplier_by_id,
                user_profile_by_user_id=user_profile_by_user_id,
                org_profile_by_org_id=org_profile_by_org_id,
                retrieval_features=session_retrieval_features.get(row["session_id"]),
            )
        )
        if index == 1 or index % 10000 == 0 or index == total_rows:
            elapsed = time.perf_counter() - started_at
            log_step(
                "Enriched rows "
                f"{index}/{total_rows} "
                f"({(index / max(total_rows, 1)) * 100:.1f}%) "
                f"elapsed={format_seconds(elapsed)}"
            )

    train_path = output_dir / "train_ranker.csv"
    val_path = output_dir / "val_ranker.csv"
    test_path = output_dir / "test_ranker.csv"

    log_step("Writing split CSV files")
    write_csv(train_path, split_rows["train"])
    write_csv(val_path, split_rows["val"])
    write_csv(test_path, split_rows["test"])

    split_counts = {name: len(rows) for name, rows in split_rows.items()}
    split_session_counts = Counter(session_split.values())
    label_distribution = {
        split: dict(Counter(row["label"] for row in rows)) for split, rows in split_rows.items()
    }

    stats = {
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "rows_total": len(relevance_rows),
        "rows_per_split": split_counts,
        "sessions_per_split": dict(split_session_counts),
        "label_distribution_per_split": label_distribution,
        "retrieval_enrichment": {
            "semantic_backend": retrieval_builder.index._semantic_backend,
            "faiss_enabled": retrieval_builder.index._semantic_faiss_index is not None,
            "semantic_enabled": getattr(retrieval_builder.index, "_semantic_enabled", False),
            "documents": len(retrieval_builder.documents),
        },
        "config": {
            "train_ratio": config.train_ratio,
            "val_ratio": config.val_ratio,
            "test_ratio": config.test_ratio,
        },
    }

    stats_path = output_dir / "split_stats.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    total_elapsed = time.perf_counter() - started_at
    print("ML splits created.")
    print(f"- train: {train_path}")
    print(f"- val:   {val_path}")
    print(f"- test:  {test_path}")
    print(f"- stats: {stats_path}")
    print(f"Rows: train={split_counts['train']}, val={split_counts['val']}, test={split_counts['test']}")
    print(f"Elapsed: {format_seconds(total_elapsed)}")


if __name__ == "__main__":
    main()
