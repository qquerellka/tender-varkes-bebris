from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    CategoryModel,
    OrgSearchProfileModel,
    OrganizationModel,
    PurchaseHistoryModel,
    SearchEventModel,
    SearchImpressionModel,
    SearchSessionModel,
    STEItemModel,
    SpellCorrectionModel,
    SupplierModel,
    SynonymModel,
    UserModel,
    UserSearchProfileModel,
)
from app.db.session import SessionLocal


@dataclass(frozen=True)
class ExportContext:
    sessions: list[SearchSessionModel]
    session_ids: set[str]
    user_ids: set[str]
    organization_ids: set[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export backend search data into an ML-friendly dataset directory."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where exported CSV/JSONL files will be written.",
    )
    parser.add_argument("--user-id", type=str, default=None)
    parser.add_argument("--organization-id", type=str, default=None)
    parser.add_argument(
        "--limit-sessions",
        type=int,
        default=None,
        help="Export only the latest N search sessions for the selected user/org scope.",
    )
    parser.add_argument(
        "--build-splits",
        action="store_true",
        help="Run ML/tools/build_ml_splits.py after export using this directory as source-dir.",
    )
    return parser.parse_args()


def to_iso(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat() + ("Z" if value.tzinfo is None else "")


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_export_context(
    session: Session,
    *,
    user_id: str | None,
    organization_id: str | None,
    limit_sessions: int | None,
) -> ExportContext:
    stmt = select(SearchSessionModel)
    if user_id:
        stmt = stmt.where(SearchSessionModel.user_id == user_id)
    if organization_id:
        stmt = stmt.where(SearchSessionModel.organization_id == organization_id)
    stmt = stmt.order_by(SearchSessionModel.created_at.desc())
    if limit_sessions:
        stmt = stmt.limit(limit_sessions)

    sessions = list(session.scalars(stmt))
    session_ids = {item.id for item in sessions}
    user_ids = {item.user_id for item in sessions}
    organization_ids = {item.organization_id for item in sessions}

    if user_id:
        user_ids.add(user_id)
    if organization_id:
        organization_ids.add(organization_id)

    return ExportContext(
        sessions=list(sorted(sessions, key=lambda item: item.created_at)),
        session_ids=session_ids,
        user_ids=user_ids,
        organization_ids=organization_ids,
    )


def export_reference_tables(session: Session, output_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}

    organizations = list(session.scalars(select(OrganizationModel).order_by(OrganizationModel.id)))
    write_csv(
        output_dir / "organizations.csv",
        [{"id": item.id, "name": item.name} for item in organizations],
        ["id", "name"],
    )
    counts["organizations"] = len(organizations)

    categories = list(session.scalars(select(CategoryModel).order_by(CategoryModel.id)))
    write_csv(
        output_dir / "categories.csv",
        [{"id": item.id, "name": item.name, "parent_id": item.parent_id or ""} for item in categories],
        ["id", "name", "parent_id"],
    )
    counts["categories"] = len(categories)

    suppliers = list(session.scalars(select(SupplierModel).order_by(SupplierModel.id)))
    write_csv(
        output_dir / "suppliers.csv",
        [{"id": item.id, "name": item.name} for item in suppliers],
        ["id", "name"],
    )
    counts["suppliers"] = len(suppliers)

    users = list(session.scalars(select(UserModel).order_by(UserModel.id)))
    write_csv(
        output_dir / "users.csv",
        [
            {
                "id": item.id,
                "organization_id": item.organization_id,
                "name": item.name,
                "role": item.role,
            }
            for item in users
        ],
        ["id", "organization_id", "name", "role"],
    )
    counts["users"] = len(users)

    ste_items = list(session.scalars(select(STEItemModel).order_by(STEItemModel.id)))
    write_csv(
        output_dir / "ste_items.csv",
        [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "category_id": item.category_id,
                "supplier_id": item.supplier_id,
                "attributes_json": json_text(item.attributes_json or {}),
                "status": item.status,
                "updated_at": to_iso(item.updated_at),
            }
            for item in ste_items
        ],
        [
            "id",
            "title",
            "description",
            "category_id",
            "supplier_id",
            "attributes_json",
            "status",
            "updated_at",
        ],
    )
    counts["ste_items"] = len(ste_items)

    synonyms = list(session.scalars(select(SynonymModel).order_by(SynonymModel.id)))
    write_csv(
        output_dir / "synonyms.csv",
        [
            {
                "id": item.id,
                "term": item.term,
                "synonym": item.synonym,
                "weight": item.weight,
                "source": item.source,
            }
            for item in synonyms
        ],
        ["id", "term", "synonym", "weight", "source"],
    )
    counts["synonyms"] = len(synonyms)

    spell_corrections = list(
        session.scalars(select(SpellCorrectionModel).order_by(SpellCorrectionModel.id))
    )
    write_csv(
        output_dir / "spell_corrections.csv",
        [
            {
                "id": item.id,
                "wrong_term": item.wrong_term,
                "correct_term": item.correct_term,
                "source": item.source,
            }
            for item in spell_corrections
        ],
        ["id", "wrong_term", "correct_term", "source"],
    )
    counts["spell_corrections"] = len(spell_corrections)

    return counts


def export_profile_tables(
    session: Session,
    output_dir: Path,
    context: ExportContext,
) -> dict[str, int]:
    counts: dict[str, int] = {}

    user_profiles_stmt = select(UserSearchProfileModel)
    if context.user_ids:
        user_profiles_stmt = user_profiles_stmt.where(UserSearchProfileModel.user_id.in_(context.user_ids))
    user_profiles = list(session.scalars(user_profiles_stmt.order_by(UserSearchProfileModel.user_id)))
    write_csv(
        output_dir / "user_search_profiles.csv",
        [
            {
                "user_id": item.user_id,
                "organization_id": item.organization_id,
                "top_categories_json": json_text(item.top_categories_json or []),
                "recent_ste_ids_json": json_text(item.recent_ste_ids_json or []),
                "top_suppliers_json": json_text(item.top_suppliers_json or []),
                "popular_queries_json": json_text(item.popular_queries_json or []),
                "updated_at": to_iso(item.updated_at),
            }
            for item in user_profiles
        ],
        [
            "user_id",
            "organization_id",
            "top_categories_json",
            "recent_ste_ids_json",
            "top_suppliers_json",
            "popular_queries_json",
            "updated_at",
        ],
    )
    counts["user_search_profiles"] = len(user_profiles)

    org_profiles_stmt = select(OrgSearchProfileModel)
    if context.organization_ids:
        org_profiles_stmt = org_profiles_stmt.where(
            OrgSearchProfileModel.organization_id.in_(context.organization_ids)
        )
    org_profiles = list(session.scalars(org_profiles_stmt.order_by(OrgSearchProfileModel.organization_id)))
    write_csv(
        output_dir / "org_search_profiles.csv",
        [
            {
                "organization_id": item.organization_id,
                "top_categories_json": json_text(item.top_categories_json or []),
                "popular_ste_ids_json": json_text(item.popular_ste_ids_json or []),
                "updated_at": to_iso(item.updated_at),
            }
            for item in org_profiles
        ],
        [
            "organization_id",
            "top_categories_json",
            "popular_ste_ids_json",
            "updated_at",
        ],
    )
    counts["org_search_profiles"] = len(org_profiles)
    return counts


def export_sessions(
    output_dir: Path,
    context: ExportContext,
) -> dict[str, int]:
    rows = [
        {
            "id": item.id,
            "user_id": item.user_id,
            "organization_id": item.organization_id,
            "query": item.query,
            "normalized_query": item.normalized_query,
            "created_at": to_iso(item.created_at),
        }
        for item in context.sessions
    ]
    write_csv(
        output_dir / "search_sessions.csv",
        rows,
        ["id", "user_id", "organization_id", "query", "normalized_query", "created_at"],
    )
    return {"search_sessions": len(rows)}


def export_events(
    session: Session,
    output_dir: Path,
    context: ExportContext,
) -> tuple[list[SearchEventModel], dict[str, int]]:
    stmt = select(SearchEventModel)
    if context.session_ids:
        stmt = stmt.where(SearchEventModel.session_id.in_(context.session_ids))
    elif context.user_ids:
        stmt = stmt.where(SearchEventModel.user_id.in_(context.user_ids))
    elif context.organization_ids:
        stmt = stmt.where(SearchEventModel.organization_id.in_(context.organization_ids))
    events = list(session.scalars(stmt.order_by(SearchEventModel.created_at.asc(), SearchEventModel.id.asc())))

    rows = [
        {
            "id": item.id,
            "session_id": item.session_id,
            "user_id": item.user_id,
            "organization_id": item.organization_id,
            "role": item.role,
            "event_type": item.event_type,
            "ste_id": item.ste_id or "",
            "supplier_id": item.supplier_id or "",
            "category_id": item.category_id or "",
            "query_text": item.query_text or "",
            "normalized_query": item.normalized_query or "",
            "corrected_query": item.corrected_query or "",
            "page_type": item.page_type or "",
            "page_url": item.page_url or "",
            "referrer": item.referrer or "",
            "rank_position": item.rank_position or "",
            "results_page": item.results_page or "",
            "payload_json": json_text(item.payload_json or {}),
            "created_at": to_iso(item.created_at),
        }
        for item in events
    ]
    write_csv(
        output_dir / "search_events.csv",
        rows,
        [
            "id",
            "session_id",
            "user_id",
            "organization_id",
            "role",
            "event_type",
            "ste_id",
            "supplier_id",
            "category_id",
            "query_text",
            "normalized_query",
            "corrected_query",
            "page_type",
            "page_url",
            "referrer",
            "rank_position",
            "results_page",
            "payload_json",
            "created_at",
        ],
    )
    write_jsonl(
        output_dir / "search_events.jsonl",
        [
            {
                **row,
                "ste_id": row["ste_id"] or None,
                "supplier_id": row["supplier_id"] or None,
                "category_id": row["category_id"] or None,
                "query_text": row["query_text"] or None,
                "normalized_query": row["normalized_query"] or None,
                "corrected_query": row["corrected_query"] or None,
                "page_type": row["page_type"] or None,
                "page_url": row["page_url"] or None,
                "referrer": row["referrer"] or None,
                "rank_position": row["rank_position"] or None,
                "results_page": row["results_page"] or None,
                "payload_json": json.loads(row["payload_json"]),
            }
            for row in rows
        ],
    )
    return events, {"search_events": len(events)}


def export_impressions(
    session: Session,
    output_dir: Path,
    context: ExportContext,
) -> tuple[list[SearchImpressionModel], dict[str, int]]:
    stmt = select(SearchImpressionModel)
    if context.session_ids:
        stmt = stmt.where(SearchImpressionModel.search_session_id.in_(context.session_ids))
    elif context.user_ids:
        stmt = stmt.where(SearchImpressionModel.user_id.in_(context.user_ids))
    elif context.organization_ids:
        stmt = stmt.where(SearchImpressionModel.organization_id.in_(context.organization_ids))
    impressions = list(
        session.scalars(
            stmt.order_by(SearchImpressionModel.rendered_at.asc(), SearchImpressionModel.id.asc())
        )
    )
    write_csv(
        output_dir / "search_impressions.csv",
        [
            {
                "id": item.id,
                "search_session_id": item.search_session_id,
                "user_id": item.user_id,
                "organization_id": item.organization_id,
                "ste_id": item.ste_id,
                "supplier_id": item.supplier_id or "",
                "category_id": item.category_id or "",
                "rank_position": item.rank_position,
                "results_page": item.results_page,
                "visible": str(bool(item.visible)).lower(),
                "rendered_at": to_iso(item.rendered_at),
            }
            for item in impressions
        ],
        [
            "id",
            "search_session_id",
            "user_id",
            "organization_id",
            "ste_id",
            "supplier_id",
            "category_id",
            "rank_position",
            "results_page",
            "visible",
            "rendered_at",
        ],
    )
    return impressions, {"search_impressions": len(impressions)}


def export_purchase_history(
    session: Session,
    output_dir: Path,
    context: ExportContext,
) -> tuple[list[PurchaseHistoryModel], dict[str, int]]:
    stmt = select(PurchaseHistoryModel)
    if context.user_ids:
        stmt = stmt.where(PurchaseHistoryModel.user_id.in_(context.user_ids))
    if context.organization_ids:
        stmt = stmt.where(PurchaseHistoryModel.organization_id.in_(context.organization_ids))
    purchase_history = list(
        session.scalars(stmt.order_by(PurchaseHistoryModel.purchased_at.asc(), PurchaseHistoryModel.id.asc()))
    )
    write_csv(
        output_dir / "purchase_history.csv",
        [
            {
                "id": item.id,
                "user_id": item.user_id,
                "organization_id": item.organization_id,
                "ste_id": item.ste_id,
                "quantity": item.quantity,
                "price": item.price,
                "purchased_at": to_iso(item.purchased_at),
            }
            for item in purchase_history
        ],
        ["id", "user_id", "organization_id", "ste_id", "quantity", "price", "purchased_at"],
    )
    return purchase_history, {"purchase_history": len(purchase_history)}


def build_query_relevance_rows(
    sessions: list[SearchSessionModel],
    impressions: list[SearchImpressionModel],
    events: list[SearchEventModel],
) -> list[dict[str, Any]]:
    session_by_id = {item.id: item for item in sessions}
    event_types_by_session_item: dict[tuple[str, str], set[str]] = defaultdict(set)

    for event in events:
        if not event.ste_id:
            continue
        event_types_by_session_item[(event.session_id, event.ste_id)].add(event.event_type)

    rows: list[dict[str, Any]] = []
    for index, impression in enumerate(impressions, start=1):
        session = session_by_id.get(impression.search_session_id)
        if session is None:
            continue
        event_types = event_types_by_session_item.get(
            (impression.search_session_id, impression.ste_id),
            set(),
        )
        clicked = int("result_clicked" in event_types)
        viewed = int(
            bool(
                {
                    "result_opened",
                    "product_view_started",
                    "product_view_ended",
                    "item_copy",
                    "favorite_added",
                    "comparison_added",
                    "cart_added",
                    "quick_back",
                }
                & event_types
            )
        )
        purchased = int("purchase_completed" in event_types)
        shortlisted = bool({"favorite_added", "comparison_added", "cart_added", "purchase_intent"} & event_types)

        if purchased:
            label = 3
        elif shortlisted:
            label = 2
        elif clicked or viewed:
            label = 1
        else:
            label = 0

        rows.append(
            {
                "row_id": str(index),
                "session_id": impression.search_session_id,
                "user_id": impression.user_id,
                "organization_id": impression.organization_id,
                "query": session.query,
                "normalized_query": session.normalized_query,
                "ste_id": impression.ste_id,
                "position": impression.rank_position,
                "label": label,
                "clicked": clicked,
                "purchased": purchased,
                "viewed": viewed,
                "created_at": to_iso(impression.rendered_at),
            }
        )
    return rows


def export_query_relevance(
    output_dir: Path,
    sessions: list[SearchSessionModel],
    impressions: list[SearchImpressionModel],
    events: list[SearchEventModel],
) -> dict[str, int]:
    rows = build_query_relevance_rows(sessions, impressions, events)
    write_csv(
        output_dir / "query_relevance.csv",
        rows,
        [
            "row_id",
            "session_id",
            "user_id",
            "organization_id",
            "query",
            "normalized_query",
            "ste_id",
            "position",
            "label",
            "clicked",
            "purchased",
            "viewed",
            "created_at",
        ],
    )
    return {"query_relevance": len(rows)}


def export_user_item_features(
    output_dir: Path,
    events: list[SearchEventModel],
    purchase_history: list[PurchaseHistoryModel],
) -> dict[str, int]:
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}

    def get_bucket(user_id: str, ste_id: str) -> dict[str, Any]:
        key = (user_id, ste_id)
        if key not in aggregates:
            aggregates[key] = {
                "user_id": user_id,
                "ste_id": ste_id,
                "click_count": 0,
                "open_count": 0,
                "favorite_count": 0,
                "compare_count": 0,
                "cart_add_count": 0,
                "cart_remove_count": 0,
                "purchase_count": 0,
                "dwell_values": [],
                "pogo_count": 0,
                "last_action_at": None,
            }
        return aggregates[key]

    for event in events:
        if not event.ste_id:
            continue
        bucket = get_bucket(event.user_id, event.ste_id)
        if event.event_type == "result_clicked":
            bucket["click_count"] += 1
        elif event.event_type == "result_opened":
            bucket["open_count"] += 1
        elif event.event_type == "favorite_added":
            bucket["favorite_count"] += 1
        elif event.event_type == "comparison_added":
            bucket["compare_count"] += 1
        elif event.event_type == "cart_added":
            bucket["cart_add_count"] += 1
        elif event.event_type == "cart_removed":
            bucket["cart_remove_count"] += 1
        elif event.event_type == "purchase_completed":
            bucket["purchase_count"] += 1
        elif event.event_type == "quick_back":
            bucket["pogo_count"] += 1
        elif event.event_type == "product_view_ended":
            dwell_ms = (event.payload_json or {}).get("dwell_ms")
            if isinstance(dwell_ms, (int, float)):
                bucket["dwell_values"].append(float(dwell_ms))

        last_action_at = bucket["last_action_at"]
        if last_action_at is None or event.created_at > last_action_at:
            bucket["last_action_at"] = event.created_at

    for item in purchase_history:
        bucket = get_bucket(item.user_id, item.ste_id)
        bucket["purchase_count"] += 1
        last_action_at = bucket["last_action_at"]
        if last_action_at is None or item.purchased_at > last_action_at:
            bucket["last_action_at"] = item.purchased_at

    rows = []
    for bucket in aggregates.values():
        dwell_values = bucket.pop("dwell_values")
        rows.append(
            {
                "user_id": bucket["user_id"],
                "ste_id": bucket["ste_id"],
                "click_count": bucket["click_count"],
                "open_count": bucket["open_count"],
                "favorite_count": bucket["favorite_count"],
                "compare_count": bucket["compare_count"],
                "cart_add_count": bucket["cart_add_count"],
                "cart_remove_count": bucket["cart_remove_count"],
                "purchase_count": bucket["purchase_count"],
                "avg_dwell_ms": round(sum(dwell_values) / len(dwell_values), 2) if dwell_values else 0,
                "pogo_count": bucket["pogo_count"],
                "last_action_at": to_iso(bucket["last_action_at"]),
            }
        )

    rows.sort(key=lambda item: (item["user_id"], item["ste_id"]))
    write_csv(
        output_dir / "user_item_features.csv",
        rows,
        [
            "user_id",
            "ste_id",
            "click_count",
            "open_count",
            "favorite_count",
            "compare_count",
            "cart_add_count",
            "cart_remove_count",
            "purchase_count",
            "avg_dwell_ms",
            "pogo_count",
            "last_action_at",
        ],
    )
    return {"user_item_features": len(rows)}


def write_metadata(
    output_dir: Path,
    *,
    args: argparse.Namespace,
    counts: dict[str, int],
) -> None:
    metadata = {
        "exported_at": to_iso(datetime.utcnow()),
        "filters": {
            "user_id": args.user_id,
            "organization_id": args.organization_id,
            "limit_sessions": args.limit_sessions,
        },
        "counts": counts,
    }
    (output_dir / "export_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def maybe_build_splits(output_dir: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "ML" / "tools" / "build_ml_splits.py"
    subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--source-dir",
            str(output_dir),
            "--output-dir",
            str(output_dir / "splits"),
        ],
        check=True,
    )


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session:
        context = load_export_context(
            session,
            user_id=args.user_id,
            organization_id=args.organization_id,
            limit_sessions=args.limit_sessions,
        )
        counts: dict[str, int] = {}
        counts.update(export_reference_tables(session, output_dir))
        counts.update(export_profile_tables(session, output_dir, context))
        counts.update(export_sessions(output_dir, context))
        events, event_counts = export_events(session, output_dir, context)
        counts.update(event_counts)
        impressions, impression_counts = export_impressions(session, output_dir, context)
        counts.update(impression_counts)
        purchase_history, purchase_counts = export_purchase_history(session, output_dir, context)
        counts.update(purchase_counts)
        counts.update(export_query_relevance(output_dir, context.sessions, impressions, events))
        counts.update(export_user_item_features(output_dir, events, purchase_history))
        write_metadata(output_dir, args=args, counts=counts)

    if args.build_splits:
        maybe_build_splits(output_dir)

    print(json.dumps({"output_dir": str(output_dir), "counts": counts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
