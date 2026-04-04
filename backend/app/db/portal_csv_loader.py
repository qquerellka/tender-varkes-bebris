from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.auth.demo import ensure_demo_profiles
from app.db.models import (
    CartItemModel,
    CategoryModel,
    ComparisonItemModel,
    FavoriteModel,
    OrgSearchProfileModel,
    OrganizationModel,
    PurchaseHistoryModel,
    SearchEventModel,
    SearchSessionModel,
    STEItemModel,
    SpellCorrectionModel,
    SupplierModel,
    SynonymModel,
    UserModel,
    UserSearchProfileModel,
)

TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9]+")
SPACE_RE = re.compile(r"\s+")

MANUFACTURER_KEYS = (
    "Производитель",
    "Производитель медицинского изделия",
    "Производитель товара",
    "Изготовитель",
    "Торговая марка",
    "Бренд",
    "Марка",
)

DEFAULT_SUPPLIER_NAME = "Поставщик не указан"
CUSTOMER_DEMO_USER_IDS = ("demo_customer_transport", "demo_customer_it")

DEFAULT_SYNONYMS = (
    ("автобус", "пассажирский транспорт", "manual", "1.0"),
    ("тюбинг", "ватрушка", "manual", "1.0"),
    ("флеш накопитель", "usb накопитель", "manual", "1.0"),
    ("ноутбук", "портативный компьютер", "manual", "0.8"),
    ("ручка", "канцелярская ручка", "manual", "0.7"),
    ("маркер", "фломастер", "manual", "0.6"),
)

DEFAULT_SPELL_CORRECTIONS = (
    ("абтобус", "автобус"),
    ("серер", "сервер"),
    ("ноутубк", "ноутбук"),
    ("картриджж", "картридж"),
    ("ватрущка", "ватрушка"),
    ("тубинг", "тюбинг"),
    ("бумга", "бумага"),
    ("марекр", "маркер"),
)


@dataclass
class SteSample:
    ste_id: str
    category_name: str
    supplier_name: str
    title_tokens: frozenset[str]
    category_tokens: frozenset[str]
    supplier_tokens: frozenset[str]


def _normalize_space(value: str) -> str:
    return SPACE_RE.sub(" ", value.replace("\u00a0", " ")).strip()


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).hexdigest()
    return f"{prefix}_{digest}"


def _extract_tokens(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value.lower()) if len(token) > 1]


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_attributes(raw_value: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    duplicate_counts: dict[str, int] = defaultdict(int)

    for chunk in raw_value.split(";"):
        part = _normalize_space(chunk)
        if not part:
            continue

        if ":" in part:
            key, value = part.split(":", 1)
        else:
            key, value = f"Атрибут {len(attributes) + 1}", part

        key = _normalize_space(key)
        value = _normalize_space(value)
        if not key or not value:
            continue

        if key in attributes:
            if attributes[key] == value:
                continue
            duplicate_counts[key] += 1
            deduplicated_key = f"{key} ({duplicate_counts[key] + 1})"
            attributes[deduplicated_key] = value
            continue

        attributes[key] = value

    return attributes


def _extract_supplier_name(title: str, attributes: dict[str, str]) -> str:
    for key in MANUFACTURER_KEYS:
        value = attributes.get(key)
        if value:
            return value[:255]

    title_tokens = title.split()
    if len(title_tokens) >= 2 and title_tokens[0].isupper():
        return " ".join(title_tokens[:2])[:255]

    return DEFAULT_SUPPLIER_NAME


def _build_description(attributes: dict[str, str]) -> str:
    parts = [f"{key}: {value}" for key, value in list(attributes.items())[:4]]
    return " ; ".join(parts)[:2000]


def _flush_rows(
    session: Session,
    model,
    rows: list[dict],
) -> int:
    if not rows:
        return 0

    session.execute(insert(model), rows)
    inserted_count = len(rows)
    rows.clear()
    session.commit()
    return inserted_count


def _truncate_tables(session: Session) -> None:
    for model in (
        SearchEventModel,
        SearchSessionModel,
        PurchaseHistoryModel,
        UserSearchProfileModel,
        OrgSearchProfileModel,
        FavoriteModel,
        ComparisonItemModel,
        CartItemModel,
        STEItemModel,
        SpellCorrectionModel,
        SynonymModel,
        UserModel,
        SupplierModel,
        CategoryModel,
        OrganizationModel,
    ):
        session.execute(delete(model))
    session.commit()


def _score_sample(
    *,
    title_tokens: set[str],
    supplier_tokens: set[str],
    sample: SteSample,
) -> float:
    title_overlap = len(title_tokens & sample.title_tokens)
    category_overlap = len(title_tokens & sample.category_tokens)
    supplier_overlap = len(supplier_tokens & sample.supplier_tokens)
    exact_supplier_match = supplier_tokens and supplier_tokens == set(sample.supplier_tokens)

    score = title_overlap * 3.0
    score += category_overlap * 1.4
    score += supplier_overlap * 2.0
    if exact_supplier_match:
        score += 4.0

    return score


def _pick_best_sample(
    *,
    title: str,
    supplier_name: str,
    token_to_category_ids: dict[str, set[str]],
    category_samples: dict[str, list[SteSample]],
) -> SteSample | None:
    title_tokens = set(_extract_tokens(title))
    supplier_tokens = set(_extract_tokens(supplier_name))
    token_counts: Counter[str] = Counter()
    for token in title_tokens:
        for category_id in token_to_category_ids.get(token, set()):
            token_counts[category_id] += 1

    if not token_counts:
        return None

    ranked_category_ids = [
        category_id
        for category_id, _ in token_counts.most_common(8)
        if category_samples.get(category_id)
    ]
    if not ranked_category_ids:
        return None

    best_sample: SteSample | None = None
    best_score = 0.0
    for category_id in ranked_category_ids:
        for sample in category_samples.get(category_id, []):
            score = _score_sample(
                title_tokens=title_tokens,
                supplier_tokens=supplier_tokens,
                sample=sample,
            )
            if score > best_score:
                best_score = score
                best_sample = sample

    return best_sample


def _remember_sample(
    samples: list[SteSample],
    sample: SteSample,
    *,
    max_items: int = 24,
) -> None:
    if len(samples) < max_items:
        samples.append(sample)
        return

    slot = int(hashlib.blake2b(sample.ste_id.encode("utf-8"), digest_size=2).hexdigest(), 16) % max_items
    samples[slot] = sample


def _seed_spell_and_synonyms(session: Session) -> dict[str, int]:
    synonym_rows = [
        {
            "id": _stable_id("syn", f"{term}:{synonym}"),
            "term": term,
            "synonym": synonym,
            "source": source,
            "weight": weight,
        }
        for term, synonym, source, weight in DEFAULT_SYNONYMS
    ]
    correction_rows = [
        {
            "id": _stable_id("corr", wrong_term),
            "wrong_term": wrong_term,
            "correct_term": correct_term,
            "source": "manual",
        }
        for wrong_term, correct_term in DEFAULT_SPELL_CORRECTIONS
    ]

    session.execute(insert(SynonymModel), synonym_rows)
    session.execute(insert(SpellCorrectionModel), correction_rows)
    session.commit()
    return {
        "synonyms": len(synonym_rows),
        "spell_corrections": len(correction_rows),
    }


def import_portal_csv_dataset(
    *,
    session: Session,
    ste_csv_path: Path,
    contracts_csv_path: Path,
    truncate: bool = True,
    ste_limit: int = 0,
    contract_limit: int = 0,
    purchase_history_limit: int = 120,
) -> dict[str, int]:
    if truncate:
        _truncate_tables(session)

    ensure_demo_profiles(session)

    stats: dict[str, int] = defaultdict(int)
    category_ids: dict[str, str] = {}
    supplier_ids: dict[str, str] = {DEFAULT_SUPPLIER_NAME: _stable_id("sup", DEFAULT_SUPPLIER_NAME)}
    pending_categories: list[dict] = []
    pending_suppliers: list[dict] = [
        {"id": supplier_ids[DEFAULT_SUPPLIER_NAME], "name": DEFAULT_SUPPLIER_NAME}
    ]
    pending_ste_items: list[dict] = []
    seen_ste_ids: set[str] = set()
    token_to_category_ids: dict[str, set[str]] = defaultdict(set)
    category_samples: dict[str, list[SteSample]] = defaultdict(list)

    with ste_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row_index, row in enumerate(reader, start=1):
            if ste_limit and row_index > ste_limit:
                break
            if len(row) != 4:
                continue

            ste_id, title, category_name, raw_attributes = row
            ste_id = _normalize_space(ste_id)
            title = _normalize_space(title)
            category_name = _normalize_space(category_name)
            if not ste_id or not title or ste_id in seen_ste_ids:
                if ste_id in seen_ste_ids:
                    stats["ste_duplicates_skipped"] += 1
                continue

            seen_ste_ids.add(ste_id)
            attributes = _parse_attributes(raw_attributes)
            supplier_name = _extract_supplier_name(title, attributes)
            description = _build_description(attributes)

            category_id = category_ids.get(category_name)
            if category_id is None:
                category_id = _stable_id("cat", category_name)
                category_ids[category_name] = category_id
                pending_categories.append({"id": category_id, "name": category_name, "parent_id": None})
                for token in set(_extract_tokens(category_name)):
                    token_to_category_ids[token].add(category_id)
            for token in set(_extract_tokens(title)):
                token_to_category_ids[token].add(category_id)

            supplier_id = supplier_ids.get(supplier_name)
            if supplier_id is None:
                supplier_id = _stable_id("sup", supplier_name)
                supplier_ids[supplier_name] = supplier_id
                pending_suppliers.append({"id": supplier_id, "name": supplier_name[:255]})

            pending_ste_items.append(
                {
                    "id": ste_id,
                    "title": title[:255],
                    "description": description,
                    "category_id": category_id,
                    "supplier_id": supplier_id,
                    "attributes_json": attributes,
                    "status": "active",
                    "updated_at": datetime.utcnow(),
                }
            )
            stats["ste_items"] += 1

            _remember_sample(
                category_samples[category_id],
                SteSample(
                    ste_id=ste_id,
                    category_name=category_name,
                    supplier_name=supplier_name,
                    title_tokens=frozenset(_extract_tokens(title)),
                    category_tokens=frozenset(_extract_tokens(category_name)),
                    supplier_tokens=frozenset(_extract_tokens(supplier_name)),
                )
            )

            if len(pending_categories) >= 500:
                stats["categories"] += _flush_rows(session, CategoryModel, pending_categories)
            if len(pending_suppliers) >= 500:
                stats["suppliers"] += _flush_rows(session, SupplierModel, pending_suppliers)
            if len(pending_ste_items) >= 2000:
                stats["ste_items_inserted"] += _flush_rows(session, STEItemModel, pending_ste_items)

    stats["categories"] += _flush_rows(session, CategoryModel, pending_categories)
    stats["suppliers"] += _flush_rows(session, SupplierModel, pending_suppliers)
    stats["ste_items_inserted"] += _flush_rows(session, STEItemModel, pending_ste_items)

    buyer_counter: Counter[tuple[str, str, str]] = Counter()
    with contracts_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row_index, row in enumerate(reader, start=1):
            if contract_limit and row_index > contract_limit:
                break
            if len(row) != 11:
                continue

            _, _, _, _, _, buyer_inn, buyer_name, buyer_region, *_ = row
            buyer_key = (
                _normalize_space(buyer_inn) or _stable_id("buyer", _normalize_space(buyer_name)),
                _normalize_space(buyer_name),
                _normalize_space(buyer_region),
            )
            buyer_counter[buyer_key] += 1

    assigned_buyers = buyer_counter.most_common(len(CUSTOMER_DEMO_USER_IDS))
    user_to_buyer: dict[str, tuple[str, str, str]] = {}
    for index, user_id in enumerate(CUSTOMER_DEMO_USER_IDS):
        if assigned_buyers:
            user_to_buyer[user_id] = assigned_buyers[min(index, len(assigned_buyers) - 1)][0]

    demo_users = {
        user_id: session.get(UserModel, user_id)
        for user_id in CUSTOMER_DEMO_USER_IDS
    }

    purchase_rows: list[dict] = []
    user_category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    user_supplier_counts: dict[str, Counter[str]] = defaultdict(Counter)
    user_query_counts: dict[str, Counter[str]] = defaultdict(Counter)
    user_recent_ste_ids: dict[str, deque[str]] = {
        user_id: deque(maxlen=12) for user_id in CUSTOMER_DEMO_USER_IDS
    }
    org_category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    org_popular_ste_counts: dict[str, Counter[str]] = defaultdict(Counter)
    user_purchase_counts: Counter[str] = Counter()

    with contracts_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row_index, row in enumerate(reader, start=1):
            if contract_limit and row_index > contract_limit:
                break
            if len(row) != 11:
                continue

            title, _, _, purchased_at, price, buyer_inn, buyer_name, buyer_region, _, contract_supplier_name, _ = row
            buyer_key = (
                _normalize_space(buyer_inn) or _stable_id("buyer", _normalize_space(buyer_name)),
                _normalize_space(buyer_name),
                _normalize_space(buyer_region),
            )

            matched_user_id = next(
                (user_id for user_id, selected_buyer in user_to_buyer.items() if buyer_key == selected_buyer),
                None,
            )
            if matched_user_id is None:
                continue

            if user_purchase_counts[matched_user_id] >= purchase_history_limit:
                continue

            sample = _pick_best_sample(
                title=title,
                supplier_name=_normalize_space(contract_supplier_name),
                token_to_category_ids=token_to_category_ids,
                category_samples=category_samples,
            )
            if sample is None:
                continue

            user_purchase_counts[matched_user_id] += 1
            purchase_id = _stable_id("purchase", f"{matched_user_id}:{row_index}:{sample.ste_id}")
            demo_user = demo_users.get(matched_user_id)
            if demo_user is None:
                continue

            organization_id = demo_user.organization_id
            query_text = " ".join(_extract_tokens(title)[:6]) or _normalize_space(title)[:80]

            purchase_rows.append(
                {
                    "id": purchase_id,
                    "user_id": matched_user_id,
                    "organization_id": organization_id,
                    "ste_id": sample.ste_id,
                    "quantity": "1",
                    "price": _normalize_space(price) or "0",
                    "purchased_at": _parse_datetime(purchased_at),
                }
            )
            user_category_counts[matched_user_id][sample.category_name] += 1
            user_supplier_counts[matched_user_id][sample.supplier_name] += 1
            user_query_counts[matched_user_id][query_text] += 1
            org_category_counts[organization_id][sample.category_name] += 1
            org_popular_ste_counts[organization_id][sample.ste_id] += 1
            if sample.ste_id not in user_recent_ste_ids[matched_user_id]:
                user_recent_ste_ids[matched_user_id].appendleft(sample.ste_id)

            if len(purchase_rows) >= 1000:
                stats["purchase_history"] += _flush_rows(session, PurchaseHistoryModel, purchase_rows)

    stats["purchase_history"] += _flush_rows(session, PurchaseHistoryModel, purchase_rows)

    profile_rows: list[dict] = []
    org_profile_rows: list[dict] = []
    for user_id in CUSTOMER_DEMO_USER_IDS:
        user = demo_users.get(user_id)
        if user is None:
            continue

        profile_rows.append(
            {
                "user_id": user_id,
                "organization_id": user.organization_id,
                "top_categories_json": [name for name, _ in user_category_counts[user_id].most_common(6)],
                "recent_ste_ids_json": list(user_recent_ste_ids[user_id]),
                "top_suppliers_json": [name for name, _ in user_supplier_counts[user_id].most_common(6)],
                "popular_queries_json": [query for query, _ in user_query_counts[user_id].most_common(8)],
                "updated_at": datetime.utcnow(),
            }
        )

    for organization_id, category_counter in org_category_counts.items():
        org_profile_rows.append(
            {
                "organization_id": organization_id,
                "top_categories_json": [name for name, _ in category_counter.most_common(6)],
                "popular_ste_ids_json": [ste_id for ste_id, _ in org_popular_ste_counts[organization_id].most_common(8)],
                "updated_at": datetime.utcnow(),
            }
        )

    if profile_rows:
        session.execute(insert(UserSearchProfileModel), profile_rows)
        session.commit()
        stats["user_search_profiles"] = len(profile_rows)

    if org_profile_rows:
        session.execute(insert(OrgSearchProfileModel), org_profile_rows)
        session.commit()
        stats["org_search_profiles"] = len(org_profile_rows)

    stats.update(_seed_spell_and_synonyms(session))
    return dict(stats)
