from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TOKEN_RE = re.compile(r"[0-9a-z\u0430-\u044f\u0451]+", flags=re.IGNORECASE)

GROUP_COL = "session_id"
LABEL_COL = "label"
DEFAULT_TOP_KS = (5, 10)
DEFAULT_POSITIVE_THRESHOLD = 2

NUMERIC_FEATURES = [
    "query_len",
    "normalized_query_len",
    "position_num",
    "query_has_correction",
    "query_has_digits",
    "query_has_synonyms",
    "cat_match_user",
    "cat_match_org",
    "supplier_match_user",
    "is_recent_ste",
    "is_popular_ste_org",
    "query_in_history",
    "retrieval_score",
    "retrieval_channel_count",
    "retrieval_exact",
    "retrieval_attribute",
    "retrieval_bm25",
    "retrieval_morphology",
    "retrieval_fuzzy",
    "retrieval_semantic",
    "retrieval_synonym",
    "retrieval_rrf",
    "channel_score_exact_structured",
    "channel_score_attribute",
    "channel_score_bm25",
    "channel_score_morphology",
    "channel_score_fuzzy",
    "channel_score_synonym_bm25",
    "channel_score_semantic",
    "channel_rank_exact_structured",
    "channel_rank_attribute",
    "channel_rank_bm25",
    "channel_rank_morphology",
    "channel_rank_fuzzy",
    "channel_rank_synonym_bm25",
    "channel_rank_semantic",
    "exact_match_flag",
    "phrase_match_flag",
    "category_match_flag",
    "brand_match_flag",
    "numeric_constraint_match_flag",
    "attribute_overlap_count",
    "appeared_in_multiple_channels",
    "strict_term_coverage",
    "fuzzy_edit_score",
    "semantic_backend_bge_m3",
    "semantic_backend_fallback",
    "semantic_via_faiss",
    "title_term_overlap",
    "description_term_overlap",
    "attribute_term_overlap",
    "total_term_overlap",
    "title_exact_match",
    "title_prefix_match",
    "title_partial_match",
    "description_contains_query",
    "attribute_value_count",
    "title_len_chars",
    "description_len_chars",
    "emb_user_centroid_sim",
    "emb_query_item_sim",
    "emb_max_recent_sim",
]

CATEGORICAL_FEATURES = [
    "item_category_id",
    "item_category_name",
    "item_supplier_id",
    "item_supplier_name",
    "item_status",
]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_splits = script_dir.parent / "data" / "orig" / "derived" / "splits"
    default_artifacts = script_dir.parent / "models" / "catboost_ranker_v1"

    parser = argparse.ArgumentParser(
        description="Train a CatBoost ranking model on prepared tender ranking splits."
    )
    parser.add_argument("--splits-dir", type=Path, default=default_splits)
    parser.add_argument("--artifacts-dir", type=Path, default=default_artifacts)
    parser.add_argument("--iterations", type=int, default=350)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--positive-threshold", type=int, default=DEFAULT_POSITIVE_THRESHOLD)
    parser.add_argument(
        "--top-ks",
        type=int,
        nargs="+",
        default=list(DEFAULT_TOP_KS),
        help="Ranking cutoffs used for evaluation, for example: --top-ks 5 10",
    )
    return parser.parse_args()


def safe_json(value: object, *, default: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if value is None:
        return default

    text = str(value).strip()
    if not text:
        return default

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("\u0451", "\u0435")
    text = re.sub(r"\s+", " ", text)
    return text


def extract_terms(value: object) -> list[str]:
    normalized = normalize_text(value)
    if not normalized:
        return []
    return TOKEN_RE.findall(normalized)


def join_attribute_values(attributes: object) -> str:
    payload = safe_json(attributes, default={})
    if not isinstance(payload, dict):
        return ""
    return " ".join(str(value) for value in payload.values() if str(value).strip())


def overlap_count(query_terms: list[str], candidate_text: str) -> float:
    if not query_terms or not candidate_text:
        return 0.0

    candidate_terms = set(extract_terms(candidate_text))
    if not candidate_terms:
        return 0.0

    return float(sum(1 for term in set(query_terms) if term in candidate_terms))


def to_string_set(value: object) -> set[str]:
    items = safe_json(value, default=[])
    if not isinstance(items, list):
        return set()
    return {normalize_text(item) for item in items if normalize_text(item)}


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()

    for column in [
        "query",
        "normalized_query",
        "item_attributes_json",
        "user_top_categories_json",
        "user_recent_ste_ids_json",
        "user_top_suppliers_json",
        "user_popular_queries_json",
        "org_top_categories_json",
        "org_popular_ste_ids_json",
        "item_title",
        "item_description",
        "item_category_id",
        "item_category_name",
        "item_supplier_id",
        "item_supplier_name",
        "item_status",
    ]:
        if column not in x.columns:
            x[column] = "{}" if column == "item_attributes_json" else "[]" if column.endswith("_json") else ""
        x[column] = x[column].fillna("").astype(str)

    x["item_title_norm"] = x["item_title"].map(normalize_text)
    x["item_description_norm"] = x["item_description"].map(normalize_text)
    x["query_norm"] = x["query"].map(normalize_text)
    x["normalized_query_norm"] = x["normalized_query"].map(normalize_text)
    x["item_attributes_text"] = x["item_attributes_json"].map(join_attribute_values)
    x["item_attributes_norm"] = x["item_attributes_text"].map(normalize_text)

    x["user_top_categories"] = x["user_top_categories_json"].map(to_string_set)
    x["user_recent_ste_ids"] = x["user_recent_ste_ids_json"].map(to_string_set)
    x["user_top_suppliers"] = x["user_top_suppliers_json"].map(to_string_set)
    x["user_popular_queries"] = x["user_popular_queries_json"].map(to_string_set)
    x["org_top_categories"] = x["org_top_categories_json"].map(to_string_set)
    x["org_popular_ste_ids"] = x["org_popular_ste_ids_json"].map(to_string_set)
    x["item_attributes_dict"] = x["item_attributes_json"].map(lambda value: safe_json(value, default={}))

    x["query_terms"] = x["normalized_query_norm"].map(extract_terms)

    x["query_len"] = x["query_norm"].str.split().str.len().fillna(0).astype(float)
    x["normalized_query_len"] = (
        x["normalized_query_norm"].str.split().str.len().fillna(0).astype(float)
    )
    x["position_num"] = pd.to_numeric(x["position"], errors="coerce").fillna(999).astype(float)
    if "query_has_correction" in x.columns:
        x["query_has_correction"] = (
            pd.to_numeric(x["query_has_correction"], errors="coerce").fillna(0).astype(float)
        )
    else:
        x["query_has_correction"] = (
            x["query_norm"] != x["normalized_query_norm"]
        ).astype(float)
    x["query_has_digits"] = x["normalized_query_norm"].str.contains(r"\d", regex=True).astype(float)
    if "query_has_synonyms" not in x.columns:
        x["query_has_synonyms"] = 0.0
    x["query_has_synonyms"] = (
        pd.to_numeric(x["query_has_synonyms"], errors="coerce").fillna(0).astype(float)
    )

    x["cat_match_user"] = x.apply(
        lambda row: float(normalize_text(row["item_category_name"]) in row["user_top_categories"]),
        axis=1,
    )
    x["cat_match_org"] = x.apply(
        lambda row: float(normalize_text(row["item_category_name"]) in row["org_top_categories"]),
        axis=1,
    )
    x["supplier_match_user"] = x.apply(
        lambda row: float(normalize_text(row["item_supplier_name"]) in row["user_top_suppliers"]),
        axis=1,
    )
    x["is_recent_ste"] = x.apply(
        lambda row: float(normalize_text(row["ste_id"]) in row["user_recent_ste_ids"]),
        axis=1,
    )
    x["is_popular_ste_org"] = x.apply(
        lambda row: float(normalize_text(row["ste_id"]) in row["org_popular_ste_ids"]),
        axis=1,
    )
    x["query_in_history"] = x.apply(
        lambda row: float(
            row["normalized_query_norm"] in row["user_popular_queries"]
            or row["query_norm"] in row["user_popular_queries"]
        ),
        axis=1,
    )

    x["title_term_overlap"] = x.apply(
        lambda row: overlap_count(row["query_terms"], row["item_title_norm"]),
        axis=1,
    )
    x["description_term_overlap"] = x.apply(
        lambda row: overlap_count(row["query_terms"], row["item_description_norm"]),
        axis=1,
    )
    x["attribute_term_overlap"] = x.apply(
        lambda row: overlap_count(row["query_terms"], row["item_attributes_norm"]),
        axis=1,
    )
    x["total_term_overlap"] = (
        x["title_term_overlap"] + x["description_term_overlap"] + x["attribute_term_overlap"]
    )

    x["title_exact_match"] = (
        x["item_title_norm"] == x["normalized_query_norm"]
    ).astype(float)
    x["title_prefix_match"] = x.apply(
        lambda row: float(
            bool(row["normalized_query_norm"])
            and row["item_title_norm"].startswith(row["normalized_query_norm"])
        ),
        axis=1,
    )
    x["title_partial_match"] = x.apply(
        lambda row: float(
            bool(row["normalized_query_norm"])
            and row["normalized_query_norm"] in row["item_title_norm"]
        ),
        axis=1,
    )
    x["description_contains_query"] = x.apply(
        lambda row: float(
            bool(row["normalized_query_norm"])
            and row["normalized_query_norm"] in row["item_description_norm"]
        ),
        axis=1,
    )

    x["attribute_value_count"] = x["item_attributes_dict"].map(
        lambda value: float(len(value) if isinstance(value, dict) else 0)
    )
    x["title_len_chars"] = x["item_title"].str.len().fillna(0).astype(float)
    x["description_len_chars"] = x["item_description"].str.len().fillna(0).astype(float)

    retrieval_numeric_defaults = {
        "retrieval_score": 0.0,
        "retrieval_channel_count": 0.0,
        "retrieval_exact": 0.0,
        "retrieval_attribute": 0.0,
        "retrieval_bm25": 0.0,
        "retrieval_morphology": 0.0,
        "retrieval_fuzzy": 0.0,
        "retrieval_semantic": 0.0,
        "retrieval_synonym": 0.0,
        "retrieval_rrf": 0.0,
        "channel_score_exact_structured": 0.0,
        "channel_score_attribute": 0.0,
        "channel_score_bm25": 0.0,
        "channel_score_morphology": 0.0,
        "channel_score_fuzzy": 0.0,
        "channel_score_synonym_bm25": 0.0,
        "channel_score_semantic": 0.0,
        "channel_rank_exact_structured": 0.0,
        "channel_rank_attribute": 0.0,
        "channel_rank_bm25": 0.0,
        "channel_rank_morphology": 0.0,
        "channel_rank_fuzzy": 0.0,
        "channel_rank_synonym_bm25": 0.0,
        "channel_rank_semantic": 0.0,
        "exact_match_flag": 0.0,
        "phrase_match_flag": 0.0,
        "category_match_flag": 0.0,
        "brand_match_flag": 0.0,
        "numeric_constraint_match_flag": 0.0,
        "attribute_overlap_count": 0.0,
        "appeared_in_multiple_channels": 0.0,
        "strict_term_coverage": 0.0,
        "fuzzy_edit_score": 0.0,
        "semantic_backend_bge_m3": 0.0,
        "semantic_backend_fallback": 0.0,
        "semantic_via_faiss": 0.0,
        "emb_user_centroid_sim": 0.0,
        "emb_query_item_sim": 0.0,
        "emb_max_recent_sim": 0.0,
    }
    for column, default in retrieval_numeric_defaults.items():
        if column not in x.columns:
            x[column] = default
        x[column] = pd.to_numeric(x[column], errors="coerce").fillna(default).astype(float)

    x[LABEL_COL] = pd.to_numeric(x[LABEL_COL], errors="coerce").fillna(0).astype(float)

    for column in CATEGORICAL_FEATURES:
        x[column] = x[column].fillna("").astype(str)

    return x


def load_split_frames(splits_dir: Path) -> dict[str, pd.DataFrame]:
    resolved = splits_dir.resolve()
    frames: dict[str, pd.DataFrame] = {}
    for split_name in ("train", "val", "test"):
        path = resolved / f"{split_name}_ranker.csv"
        frames[split_name] = pd.read_csv(path)
    return frames


def sort_for_ranking(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.copy()
    ordered["position_num"] = pd.to_numeric(ordered["position_num"], errors="coerce").fillna(999)
    sort_columns = [GROUP_COL, "position_num"]
    if "ste_id" in ordered.columns:
        sort_columns.append("ste_id")
    return ordered.sort_values(sort_columns).reset_index(drop=True)


def feature_columns() -> list[str]:
    return [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES]


def build_group_ids(df: pd.DataFrame) -> np.ndarray:
    return pd.factorize(df[GROUP_COL], sort=True)[0].astype(int)


def position_baseline_scores(df: pd.DataFrame) -> pd.Series:
    return -pd.to_numeric(df["position_num"], errors="coerce").fillna(999.0)


def dcg_at_k(relevances: np.ndarray, k: int) -> float:
    rel = np.asarray(relevances, dtype=float)[:k]
    if rel.size == 0:
        return 0.0
    denom = np.log2(np.arange(2, rel.size + 2))
    return float(np.sum((2**rel - 1) / denom))


def average_precision_at_k(binary_relevance: np.ndarray, k: int) -> float:
    rel = np.asarray(binary_relevance, dtype=float)[:k]
    if rel.size == 0 or rel.sum() == 0:
        return 0.0

    precisions = []
    hits = 0.0
    for index, value in enumerate(rel, start=1):
        if value <= 0:
            continue
        hits += 1
        precisions.append(hits / index)
    return float(np.mean(precisions)) if precisions else 0.0


def evaluate_ranking(
    df: pd.DataFrame,
    *,
    pred_col: str,
    top_ks: tuple[int, ...] | list[int] = DEFAULT_TOP_KS,
    positive_threshold: int = DEFAULT_POSITIVE_THRESHOLD,
) -> dict[str, float]:
    metrics: dict[str, float] = {}
    grouped = list(df.groupby(GROUP_COL, sort=False))

    for top_k in top_ks:
        ndcgs: list[float] = []
        mrrs: list[float] = []
        hit_rates: list[float] = []
        aps: list[float] = []

        for _, group in grouped:
            ideal = dcg_at_k(
                group.sort_values(LABEL_COL, ascending=False)[LABEL_COL].to_numpy(),
                top_k,
            )
            predicted = group.sort_values(pred_col, ascending=False)
            predicted_labels = predicted[LABEL_COL].to_numpy()

            if ideal > 0:
                ndcgs.append(dcg_at_k(predicted_labels, top_k) / ideal)

            positive = (predicted_labels[:top_k] >= positive_threshold).astype(float)
            hit_rates.append(float(positive.any()))
            aps.append(average_precision_at_k(positive, top_k))

            positive_indexes = np.where(positive > 0)[0]
            if positive_indexes.size == 0:
                mrrs.append(0.0)
            else:
                mrrs.append(1.0 / float(positive_indexes[0] + 1))

        metrics[f"ndcg@{top_k}"] = float(np.mean(ndcgs)) if ndcgs else 0.0
        metrics[f"hit_rate@{top_k}"] = float(np.mean(hit_rates)) if hit_rates else 0.0
        metrics[f"mrr@{top_k}"] = float(np.mean(mrrs)) if mrrs else 0.0
        metrics[f"map@{top_k}"] = float(np.mean(aps)) if aps else 0.0

    return metrics


def import_catboost() -> tuple[Any, Any]:
    try:
        from catboost import CatBoostRanker, Pool
    except ImportError as exc:  # pragma: no cover - depends on local env
        raise SystemExit(
            "CatBoost is not installed. Install dependencies from ML/requirements-notebook.txt "
            "or add catboost to your training environment."
        ) from exc

    return CatBoostRanker, Pool


def build_catboost_pool(df: pd.DataFrame, *, pool_cls: Any) -> Any:
    ordered = sort_for_ranking(df)
    features = ordered[feature_columns()].copy()
    group_ids = build_group_ids(ordered)
    cat_features = [features.columns.get_loc(column) for column in CATEGORICAL_FEATURES]

    return pool_cls(
        data=features,
        label=ordered[LABEL_COL].astype(float).to_numpy(),
        group_id=group_ids,
        cat_features=cat_features,
        feature_names=feature_columns(),
    )


def train_catboost_ranker(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    *,
    iterations: int = 350,
    learning_rate: float = 0.05,
    depth: int = 6,
    random_seed: int = 42,
) -> tuple[Any, dict[str, Any]]:
    ranker_cls, pool_cls = import_catboost()
    train_pool = build_catboost_pool(train_df, pool_cls=pool_cls)
    val_pool = build_catboost_pool(val_df, pool_cls=pool_cls)

    params = {
        "loss_function": "YetiRankPairwise",
        "eval_metric": "NDCG:top=10",
        "iterations": iterations,
        "learning_rate": learning_rate,
        "depth": depth,
        "random_seed": random_seed,
        "verbose": 50,
    }

    model = ranker_cls(**params)
    model.fit(train_pool, eval_set=val_pool, use_best_model=True)
    return model, params


def predict_scores(model: Any, df: pd.DataFrame) -> np.ndarray:
    ordered = df.copy()
    ordered["_row_id"] = np.arange(len(ordered))
    ordered = sort_for_ranking(ordered)
    features = ordered[feature_columns()].copy()
    predictions = model.predict(features)
    ordered = ordered.copy()
    ordered["prediction"] = predictions
    return ordered.sort_values("_row_id")["prediction"].to_numpy()


def feature_importance_frame(model: Any, train_df: pd.DataFrame) -> pd.DataFrame:
    _, pool_cls = import_catboost()
    train_pool = build_catboost_pool(train_df, pool_cls=pool_cls)
    values = model.get_feature_importance(
        data=train_pool,
        type="FeatureImportance",
    )
    frame = pd.DataFrame({"feature": feature_columns(), "importance": values})
    return frame.sort_values("importance", ascending=False).reset_index(drop=True)


def save_artifacts(
    *,
    model: Any,
    artifacts_dir: Path,
    params: dict[str, Any],
    metrics: dict[str, Any],
    importance: pd.DataFrame,
) -> None:
    resolved = artifacts_dir.resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    model.save_model(str(resolved / "catboost_ranker.cbm"))
    (resolved / "model_info.json").write_text(
        json.dumps(
            {
                "model_type": "catboost_ranker",
                "numeric_features": NUMERIC_FEATURES,
                "categorical_features": CATEGORICAL_FEATURES,
                "feature_columns": feature_columns(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (resolved / "params.json").write_text(
        json.dumps(params, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (resolved / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    importance.to_csv(resolved / "feature_importance.csv", index=False, encoding="utf-8")


def run_training_pipeline(
    *,
    splits_dir: Path,
    artifacts_dir: Path,
    iterations: int,
    learning_rate: float,
    depth: int,
    random_seed: int,
    top_ks: tuple[int, ...] | list[int],
    positive_threshold: int,
) -> dict[str, Any]:
    frames = load_split_frames(splits_dir)
    train_df = build_features(frames["train"])
    val_df = build_features(frames["val"])
    test_df = build_features(frames["test"])

    model, params = train_catboost_ranker(
        train_df,
        val_df,
        iterations=iterations,
        learning_rate=learning_rate,
        depth=depth,
        random_seed=random_seed,
    )

    baseline_metrics = {
        "val": evaluate_ranking(
            val_df.assign(position_baseline=position_baseline_scores(val_df)),
            pred_col="position_baseline",
            top_ks=top_ks,
            positive_threshold=positive_threshold,
        ),
        "test": evaluate_ranking(
            test_df.assign(position_baseline=position_baseline_scores(test_df)),
            pred_col="position_baseline",
            top_ks=top_ks,
            positive_threshold=positive_threshold,
        ),
    }

    val_pred = predict_scores(model, val_df)
    test_pred = predict_scores(model, test_df)

    catboost_metrics = {
        "val": evaluate_ranking(
            val_df.assign(prediction=val_pred),
            pred_col="prediction",
            top_ks=top_ks,
            positive_threshold=positive_threshold,
        ),
        "test": evaluate_ranking(
            test_df.assign(prediction=test_pred),
            pred_col="prediction",
            top_ks=top_ks,
            positive_threshold=positive_threshold,
        ),
    }

    metrics = {
        "rows": {
            "train": int(len(train_df)),
            "val": int(len(val_df)),
            "test": int(len(test_df)),
        },
        "groups": {
            "train": int(train_df[GROUP_COL].nunique()),
            "val": int(val_df[GROUP_COL].nunique()),
            "test": int(test_df[GROUP_COL].nunique()),
        },
        "positive_threshold": int(positive_threshold),
        "top_ks": list(top_ks),
        "baseline_position": baseline_metrics,
        "catboost_ranker": catboost_metrics,
    }

    importance = feature_importance_frame(model, train_df)
    save_artifacts(
        model=model,
        artifacts_dir=artifacts_dir,
        params=params,
        metrics=metrics,
        importance=importance,
    )

    return {
        "metrics": metrics,
        "params": params,
        "feature_importance": importance,
    }


def main() -> None:
    args = parse_args()
    result = run_training_pipeline(
        splits_dir=args.splits_dir,
        artifacts_dir=args.artifacts_dir,
        iterations=args.iterations,
        learning_rate=args.learning_rate,
        depth=args.depth,
        random_seed=args.random_seed,
        top_ks=tuple(args.top_ks),
        positive_threshold=args.positive_threshold,
    )

    print("CatBoost ranker training finished.")
    print(f"Artifacts: {args.artifacts_dir.resolve()}")
    print(
        json.dumps(
            {
                "params": result["params"],
                "test_metrics": result["metrics"]["catboost_ranker"]["test"],
                "baseline_test_metrics": result["metrics"]["baseline_position"]["test"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
