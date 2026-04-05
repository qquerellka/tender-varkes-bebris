from __future__ import annotations

import argparse
import csv
import json
import pickle
import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from retrieval_feature_enrichment import RetrievalFeatureBuilder
except Exception:  # pragma: no cover - optional dependency for enrichment-only flows
    try:
        from .retrieval_feature_enrichment import RetrievalFeatureBuilder  # type: ignore[no-redef]
    except Exception:  # pragma: no cover - dataset build can run without enrichment
        RetrievalFeatureBuilder = Any  # type: ignore[misc,assignment]

from app.domain.search.normalizer import extract_query_terms, normalize_query

SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-zA-Zа-яА-Я0-9]+")
PROGRESS_EVERY = 10_000

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


@dataclass(frozen=True)
class BuildConfig:
    contract_limit: int
    max_organizations: int
    max_contracts_per_org: int
    candidate_limit: int
    visible_limit: int
    query_term_limit: int
    min_query_terms: int
    min_match_score: float
    max_samples_per_category: int


@dataclass
class SteSample:
    ste_id: str
    title: str
    description: str
    category_id: str
    category_name: str
    supplier_id: str
    supplier_name: str
    attributes_json: str
    title_tokens: frozenset[str]
    category_tokens: frozenset[str]
    supplier_tokens: frozenset[str]


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_input_dir = script_dir.parent / "data" / "orig"
    default_output_dir = default_input_dir / "derived"

    parser = argparse.ArgumentParser(
        description="Build a compact ML-ready ranking dataset from portal STE and contracts CSV."
    )
    parser.add_argument(
        "--phase",
        choices=("all", "catalog", "buyers", "dataset"),
        default="all",
        help="Run a single resumable phase or the whole pipeline.",
    )
    parser.add_argument("--input-dir", type=Path, default=default_input_dir)
    parser.add_argument("--output-dir", type=Path, default=default_output_dir)
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=None,
        help="Directory for resumable intermediate artifacts. Defaults to <output-dir>/_state.",
    )
    parser.add_argument("--ste-csv", type=Path, default=None)
    parser.add_argument("--contracts-csv", type=Path, default=None)
    parser.add_argument("--contract-limit", type=int, default=500_000)
    parser.add_argument("--max-organizations", type=int, default=120)
    parser.add_argument("--max-contracts-per-org", type=int, default=60)
    parser.add_argument("--candidate-limit", type=int, default=15)
    parser.add_argument("--visible-limit", type=int, default=8)
    parser.add_argument("--query-term-limit", type=int, default=6)
    parser.add_argument("--min-query-terms", type=int, default=1)
    parser.add_argument("--min-match-score", type=float, default=2.0)
    parser.add_argument("--max-samples-per-category", type=int, default=12)
    return parser.parse_args()


def _normalize_space(value: str) -> str:
    return SPACE_RE.sub(" ", value.replace("\u00a0", " ")).strip()


def _stable_id(prefix: str, value: str) -> str:
    import hashlib

    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).hexdigest()
    return f"{prefix}_{digest}"


def _extract_tokens(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(value.lower()) if len(token) > 1]


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
            key = f"{key} ({duplicate_counts[key] + 1})"

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


def _score_sample(
    *,
    title_tokens: set[str],
    supplier_tokens: set[str],
    sample: SteSample,
) -> float:
    title_overlap = len(title_tokens & sample.title_tokens)
    category_overlap = len(title_tokens & sample.category_tokens)
    supplier_overlap = len(supplier_tokens & sample.supplier_tokens)
    exact_supplier_match = bool(supplier_tokens) and supplier_tokens == set(sample.supplier_tokens)

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
) -> tuple[SteSample | None, float]:
    title_tokens = set(_extract_tokens(title))
    supplier_tokens = set(_extract_tokens(supplier_name))
    token_counts: Counter[str] = Counter()
    for token in title_tokens:
        for category_id in token_to_category_ids.get(token, set()):
            token_counts[category_id] += 1

    if not token_counts:
        return None, 0.0

    ranked_category_ids = [
        category_id
        for category_id, _ in token_counts.most_common(10)
        if category_samples.get(category_id)
    ]
    if not ranked_category_ids:
        return None, 0.0

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

    return best_sample, best_score


def _build_candidate_ids(
    *,
    title: str,
    supplier_name: str,
    token_to_category_ids: dict[str, set[str]],
    category_samples: dict[str, list[SteSample]],
    limit: int,
) -> list[str]:
    title_tokens = set(_extract_tokens(title))
    supplier_tokens = set(_extract_tokens(supplier_name))
    token_counts: Counter[str] = Counter()
    for token in title_tokens:
        for category_id in token_to_category_ids.get(token, set()):
            token_counts[category_id] += 1

    candidate_scores: dict[str, float] = {}
    for category_id, category_hits in token_counts.most_common(12):
        for sample in category_samples.get(category_id, []):
            score = _score_sample(
                title_tokens=title_tokens,
                supplier_tokens=supplier_tokens,
                sample=sample,
            )
            score += category_hits * 0.25
            previous = candidate_scores.get(sample.ste_id)
            if previous is None or score > previous:
                candidate_scores[sample.ste_id] = score

    ranked_candidates = sorted(
        candidate_scores.items(),
        key=lambda item: (-item[1], item[0]),
    )
    return [ste_id for ste_id, _ in ranked_candidates[:limit]]


def _remember_sample(
    samples: list[SteSample],
    sample: SteSample,
    *,
    max_items: int,
) -> None:
    if len(samples) < max_items:
        samples.append(sample)
        return

    slot = int(_stable_id("slot", sample.ste_id).split("_", 1)[1][:4], 16) % max_items
    samples[slot] = sample


def _resolve_input_file(
    explicit_path: Path | None,
    *,
    search_root: Path,
    pattern: str,
) -> Path:
    if explicit_path is not None:
        return explicit_path.resolve()

    candidates = sorted(search_root.rglob(pattern))
    if not candidates:
        raise FileNotFoundError(f"Could not find input file matching {pattern!r} under {search_root}")
    return candidates[0].resolve()


def _parse_contract_datetime(value: str) -> datetime:
    cleaned = _normalize_space(value)
    if not cleaned:
        return datetime.now(UTC)

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(cleaned, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return datetime.fromisoformat(cleaned).astimezone(UTC)


def _build_query_text(
    *,
    contract_title: str,
    sample: SteSample,
    query_term_limit: int,
) -> str:
    contract_terms = extract_query_terms(normalize_query(contract_title))
    sample_terms = set(extract_query_terms(normalize_query(sample.title)))
    query_terms: list[str] = []

    for term in contract_terms:
        if term in sample_terms and term not in query_terms:
            query_terms.append(term)
        if len(query_terms) >= query_term_limit:
            break

    if len(query_terms) < min(2, query_term_limit):
        for term in contract_terms:
            if term not in query_terms:
                query_terms.append(term)
            if len(query_terms) >= query_term_limit:
                break

    if len(query_terms) < min(2, query_term_limit):
        for term in extract_query_terms(normalize_query(sample.category_name)):
            if term not in query_terms:
                query_terms.append(term)
            if len(query_terms) >= query_term_limit:
                break

    return " ".join(query_terms).strip()


def _soft_label(
    *,
    candidate: dict[str, str],
    positive_sample: SteSample,
    query_terms: list[str],
) -> int:
    if candidate["id"] == positive_sample.ste_id:
        return 3

    title_terms = set(extract_query_terms(normalize_query(candidate.get("title", ""))))
    description_terms = set(extract_query_terms(normalize_query(candidate.get("description", ""))))
    overlap = len(set(query_terms) & (title_terms | description_terms))
    category_match = candidate.get("category_id") == positive_sample.category_id
    supplier_match = candidate.get("supplier_id") == positive_sample.supplier_id

    if category_match and overlap > 0:
        return 1
    if supplier_match and overlap >= 2:
        return 1
    if overlap >= max(2, min(len(set(query_terms)), 3)):
        return 1
    return 0


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _print_progress(stage: str, row_index: int, **metrics: int) -> None:
    details = ", ".join(f"{name}={value}" for name, value in metrics.items())
    suffix = f" ({details})" if details else ""
    print(f"[build_portal_dataset] {stage}: scanned={row_index}{suffix}", flush=True)


def _resolve_state_dir(output_dir: Path, explicit_state_dir: Path | None) -> Path:
    if explicit_state_dir is not None:
        return explicit_state_dir.resolve()
    return output_dir / "_state"


def _catalog_snapshot_path(state_dir: Path) -> Path:
    return state_dir / "catalog_snapshot.pkl"


def _selected_buyers_path(state_dir: Path) -> Path:
    return state_dir / "selected_buyers.json"


def _save_catalog_snapshot(
    *,
    state_dir: Path,
    item_by_id: dict[str, dict[str, str]],
    category_by_id: dict[str, dict[str, str]],
    supplier_by_id: dict[str, dict[str, str]],
    token_to_category_ids: dict[str, set[str]],
    category_samples: dict[str, list[SteSample]],
    catalog_stats: dict[str, int],
) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "item_by_id": item_by_id,
        "category_by_id": category_by_id,
        "supplier_by_id": supplier_by_id,
        "token_to_category_ids": token_to_category_ids,
        "category_samples": category_samples,
        "catalog_stats": catalog_stats,
    }
    with _catalog_snapshot_path(state_dir).open("wb") as handle:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)


def _load_catalog_snapshot(
    state_dir: Path,
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, set[str]],
    dict[str, list[SteSample]],
    dict[str, int],
]:
    snapshot_path = _catalog_snapshot_path(state_dir)
    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"Catalog snapshot is missing: {snapshot_path}. Run --phase catalog first."
        )
    with snapshot_path.open("rb") as handle:
        payload = pickle.load(handle)
    return (
        payload["item_by_id"],
        payload["category_by_id"],
        payload["supplier_by_id"],
        payload["token_to_category_ids"],
        payload["category_samples"],
        payload["catalog_stats"],
    )


def _save_selected_buyers(
    *,
    state_dir: Path,
    selected_buyers: set[tuple[str, str, str]],
    buyer_stats: dict[str, Any],
) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "selected_buyers": [
            {
                "buyer_id": buyer_id,
                "buyer_name": buyer_name,
                "buyer_region": buyer_region,
            }
            for buyer_id, buyer_name, buyer_region in sorted(selected_buyers)
        ],
        "stats": buyer_stats,
    }
    _selected_buyers_path(state_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _load_selected_buyers(state_dir: Path) -> tuple[set[tuple[str, str, str]], dict[str, Any]]:
    selected_buyers_file = _selected_buyers_path(state_dir)
    if not selected_buyers_file.exists():
        raise FileNotFoundError(
            f"Selected buyers snapshot is missing: {selected_buyers_file}. Run --phase buyers first."
        )
    payload = json.loads(selected_buyers_file.read_text(encoding="utf-8"))
    selected_buyers = {
        (
            row["buyer_id"],
            row["buyer_name"],
            row["buyer_region"],
        )
        for row in payload.get("selected_buyers", [])
    }
    return selected_buyers, payload.get("stats", {})


def _build_default_synonym_rows() -> list[dict[str, str]]:
    return [
        {
            "id": _stable_id("syn", f"{term}:{synonym}"),
            "term": term,
            "synonym": synonym,
            "weight": weight,
            "source": source,
        }
        for term, synonym, source, weight in DEFAULT_SYNONYMS
    ]


def _build_default_spell_rows() -> list[dict[str, str]]:
    return [
        {
            "id": _stable_id("spell", wrong_term),
            "wrong_term": wrong_term,
            "correct_term": correct_term,
            "source": "manual",
        }
        for wrong_term, correct_term in DEFAULT_SPELL_CORRECTIONS
    ]


def _build_sampled_catalog(
    *,
    ste_csv_path: Path,
    max_samples_per_category: int,
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, set[str]],
    dict[str, list[SteSample]],
    dict[str, int],
]:
    token_to_category_ids: dict[str, set[str]] = defaultdict(set)
    category_samples: dict[str, list[SteSample]] = defaultdict(list)
    category_id_by_name: dict[str, str] = {}
    supplier_id_by_name: dict[str, str] = {
        DEFAULT_SUPPLIER_NAME: _stable_id("sup", DEFAULT_SUPPLIER_NAME)
    }
    stats: Counter[str] = Counter()

    with ste_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row in reader:
            stats["ste_rows_scanned"] += 1
            if stats["ste_rows_scanned"] % PROGRESS_EVERY == 0:
                _print_progress(
                    "ste_catalog",
                    stats["ste_rows_scanned"],
                    categories=len(category_id_by_name),
                    sampled_items=sum(len(samples) for samples in category_samples.values()),
                )
            if len(row) != 4:
                stats["ste_rows_skipped_bad_schema"] += 1
                continue

            ste_id, title, category_name, raw_attributes = row
            ste_id = _normalize_space(ste_id)
            title = _normalize_space(title)
            category_name = _normalize_space(category_name)
            if not ste_id or not title or not category_name:
                stats["ste_rows_skipped_empty"] += 1
                continue

            attributes = _parse_attributes(raw_attributes)
            supplier_name = _extract_supplier_name(title, attributes)
            description = _build_description(attributes)

            category_id = category_id_by_name.setdefault(category_name, _stable_id("cat", category_name))
            supplier_id = supplier_id_by_name.setdefault(
                supplier_name,
                _stable_id("sup", supplier_name),
            )

            for token in set(_extract_tokens(category_name)):
                token_to_category_ids[token].add(category_id)
            for token in set(_extract_tokens(title)):
                token_to_category_ids[token].add(category_id)

            sample = SteSample(
                ste_id=ste_id,
                title=title[:255],
                description=description,
                category_id=category_id,
                category_name=category_name,
                supplier_id=supplier_id,
                supplier_name=supplier_name[:255],
                attributes_json=json.dumps(attributes, ensure_ascii=False),
                title_tokens=frozenset(_extract_tokens(title)),
                category_tokens=frozenset(_extract_tokens(category_name)),
                supplier_tokens=frozenset(_extract_tokens(supplier_name)),
            )
            _remember_sample(
                category_samples[category_id],
                sample,
                max_items=max_samples_per_category,
            )

    item_by_id: dict[str, dict[str, str]] = {}
    category_by_id: dict[str, dict[str, str]] = {}
    supplier_by_id: dict[str, dict[str, str]] = {}

    for samples in category_samples.values():
        for sample in samples:
            item_by_id[sample.ste_id] = {
                "id": sample.ste_id,
                "title": sample.title,
                "description": sample.description,
                "category_id": sample.category_id,
                "supplier_id": sample.supplier_id,
                "attributes_json": sample.attributes_json,
                "status": "active",
                "updated_at": datetime.now(UTC).isoformat(),
            }
            category_by_id[sample.category_id] = {
                "id": sample.category_id,
                "name": sample.category_name,
                "parent_id": "",
            }
            supplier_by_id[sample.supplier_id] = {
                "id": sample.supplier_id,
                "name": sample.supplier_name,
            }

    stats["sampled_catalog_items"] = len(item_by_id)
    stats["sampled_categories"] = len(category_by_id)
    stats["sampled_suppliers"] = len(supplier_by_id)

    return (
        item_by_id,
        category_by_id,
        supplier_by_id,
        token_to_category_ids,
        category_samples,
        dict(stats),
    )


def _scan_buyer_counts(
    *,
    contracts_csv_path: Path,
    contract_limit: int,
) -> Counter[tuple[str, str, str]]:
    buyer_counter: Counter[tuple[str, str, str]] = Counter()
    with contracts_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row_index, row in enumerate(reader, start=1):
            if contract_limit and row_index > contract_limit:
                break
            if row_index % PROGRESS_EVERY == 0:
                _print_progress(
                    "contracts_buyer_scan",
                    row_index,
                    unique_buyers=len(buyer_counter),
                )
            if len(row) != 11:
                continue

            _, _, _, _, _, buyer_inn, buyer_name, buyer_region, *_ = row
            buyer_key = (
                _normalize_space(buyer_inn) or _stable_id("buyer", _normalize_space(buyer_name)),
                _normalize_space(buyer_name),
                _normalize_space(buyer_region),
            )
            buyer_counter[buyer_key] += 1
    return buyer_counter


def _select_buyers(
    *,
    contracts_csv_path: Path,
    contract_limit: int,
    max_organizations: int,
) -> tuple[set[tuple[str, str, str]], dict[str, Any]]:
    buyer_counter = _scan_buyer_counts(
        contracts_csv_path=contracts_csv_path,
        contract_limit=contract_limit,
    )
    ranked_buyers = buyer_counter.most_common(max_organizations)
    selected_buyers = {buyer_key for buyer_key, _ in ranked_buyers}
    stats = {
        "contract_limit": contract_limit,
        "buyers_scanned": len(buyer_counter),
        "buyers_selected": len(selected_buyers),
        "top_buyers": [
            {
                "buyer_id": buyer_key[0],
                "buyer_name": buyer_key[1],
                "buyer_region": buyer_key[2],
                "contracts": count,
            }
            for buyer_key, count in ranked_buyers[: min(20, len(ranked_buyers))]
        ],
    }
    return selected_buyers, stats


def _build_dataset_rows(
    *,
    contracts_csv_path: Path,
    item_by_id: dict[str, dict[str, str]],
    token_to_category_ids: dict[str, set[str]],
    category_samples: dict[str, list[SteSample]],
    retrieval_builder: RetrievalFeatureBuilder | None,
    config: BuildConfig,
    selected_buyers: set[tuple[str, str, str]] | None = None,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    if selected_buyers is None:
        selected_buyers, _ = _select_buyers(
            contracts_csv_path=contracts_csv_path,
            contract_limit=config.contract_limit,
            max_organizations=config.max_organizations,
        )

    stats: Counter[str] = Counter()
    stats["buyers_selected"] = len(selected_buyers)

    organizations: dict[str, dict[str, str]] = {}
    users: dict[str, dict[str, str]] = {}
    purchase_rows: list[dict[str, str]] = []
    query_relevance_rows: list[dict[str, str]] = []
    user_category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    user_supplier_counts: dict[str, Counter[str]] = defaultdict(Counter)
    user_query_counts: dict[str, Counter[str]] = defaultdict(Counter)
    user_recent_ste_ids: dict[str, deque[str]] = defaultdict(lambda: deque(maxlen=12))
    org_category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    org_popular_ste_counts: dict[str, Counter[str]] = defaultdict(Counter)
    accepted_contracts_per_org: Counter[str] = Counter()
    row_id = 1

    with contracts_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, delimiter=";")
        for row_index, row in enumerate(reader, start=1):
            if config.contract_limit and row_index > config.contract_limit:
                break
            if row_index % PROGRESS_EVERY == 0:
                _print_progress(
                    "contracts_dataset",
                    row_index,
                    sessions_created=stats["sessions_created"],
                    query_relevance_rows=len(query_relevance_rows),
                )
            if len(row) != 11:
                stats["contracts_skipped_bad_schema"] += 1
                continue

            (
                title,
                _contract_id,
                _ste_external_id,
                purchased_at_raw,
                price,
                buyer_inn,
                buyer_name,
                buyer_region,
                _supplier_inn,
                contract_supplier_name,
                _supplier_region,
            ) = row

            buyer_key = (
                _normalize_space(buyer_inn) or _stable_id("buyer", _normalize_space(buyer_name)),
                _normalize_space(buyer_name),
                _normalize_space(buyer_region),
            )
            if buyer_key not in selected_buyers:
                continue

            org_id = _stable_id("org", "::".join(buyer_key))
            if accepted_contracts_per_org[org_id] >= config.max_contracts_per_org:
                stats["contracts_skipped_org_cap"] += 1
                continue

            sample, match_score = _pick_best_sample(
                title=title,
                supplier_name=_normalize_space(contract_supplier_name),
                token_to_category_ids=token_to_category_ids,
                category_samples=category_samples,
            )
            if sample is None:
                stats["contracts_skipped_no_sample_match"] += 1
                continue
            if match_score < config.min_match_score:
                stats["contracts_skipped_low_match_score"] += 1
                continue

            query_text = _build_query_text(
                contract_title=title,
                sample=sample,
                query_term_limit=config.query_term_limit,
            )
            query_terms = extract_query_terms(normalize_query(query_text))
            if len(query_terms) < config.min_query_terms:
                stats["contracts_skipped_short_query"] += 1
                continue

            normalized_query = normalize_query(query_text)
            if retrieval_builder is not None:
                candidate_pool_ids = _build_candidate_ids(
                    title=title,
                    supplier_name=_normalize_space(contract_supplier_name),
                    token_to_category_ids=token_to_category_ids,
                    category_samples=category_samples,
                    limit=max(config.candidate_limit * 12, 120),
                )
                if sample.ste_id not in candidate_pool_ids:
                    candidate_pool_ids.append(sample.ste_id)
                _, retrieval_results = retrieval_builder.search(
                    query=query_text,
                    normalized_query=normalized_query,
                    candidate_item_ids=set(candidate_pool_ids),
                    limit=max(config.candidate_limit * 4, 60),
                )
                candidate_ids = [
                    result.document_id
                    for result in retrieval_results[: config.candidate_limit]
                ]
            else:
                candidate_ids = _build_candidate_ids(
                    title=title,
                    supplier_name=_normalize_space(contract_supplier_name),
                    token_to_category_ids=token_to_category_ids,
                    category_samples=category_samples,
                    limit=config.candidate_limit,
                )
            if sample.ste_id not in candidate_ids:
                stats["contracts_skipped_positive_not_in_top_k"] += 1
                continue

            created_at = _parse_contract_datetime(purchased_at_raw).isoformat().replace("+00:00", "Z")
            user_id = _stable_id("user", f"{org_id}:{buyer_key[1]}")
            session_id = _stable_id("session", f"{row_index}:{user_id}:{sample.ste_id}:{query_text}")

            organizations.setdefault(
                org_id,
                {
                    "id": org_id,
                    "name": buyer_key[1][:255] or buyer_key[0],
                },
            )
            users.setdefault(
                user_id,
                {
                    "id": user_id,
                    "organization_id": org_id,
                    "name": (buyer_key[1][:255] or "Покупатель"),
                    "role": "customer",
                },
            )
            purchase_rows.append(
                {
                    "id": _stable_id("purchase", f"{row_index}:{user_id}:{sample.ste_id}"),
                    "user_id": user_id,
                    "organization_id": org_id,
                    "ste_id": sample.ste_id,
                    "quantity": "1",
                    "price": _normalize_space(price) or "0",
                    "purchased_at": created_at,
                }
            )

            user_category_counts[user_id][sample.category_name] += 1
            user_supplier_counts[user_id][sample.supplier_name] += 1
            user_query_counts[user_id][query_text] += 1
            org_category_counts[org_id][sample.category_name] += 1
            org_popular_ste_counts[org_id][sample.ste_id] += 1
            if sample.ste_id not in user_recent_ste_ids[user_id]:
                user_recent_ste_ids[user_id].appendleft(sample.ste_id)

            visible_limit = max(1, min(config.visible_limit, len(candidate_ids)))
            for position, candidate_id in enumerate(candidate_ids, start=1):
                candidate = item_by_id[candidate_id]
                is_positive = candidate["id"] == sample.ste_id
                label = 3 if is_positive else _soft_label(
                    candidate=candidate,
                    positive_sample=sample,
                    query_terms=query_terms,
                )
                query_relevance_rows.append(
                    {
                        "row_id": str(row_id),
                        "session_id": session_id,
                        "user_id": user_id,
                        "organization_id": org_id,
                        "query": query_text,
                        "normalized_query": normalized_query,
                        "ste_id": candidate["id"],
                        "position": str(position),
                        "label": str(label),
                        "clicked": "1" if is_positive else "0",
                        "purchased": "1" if is_positive else "0",
                        "viewed": "1" if (position <= visible_limit or is_positive) else "0",
                        "created_at": created_at,
                    }
                )
                row_id += 1

            accepted_contracts_per_org[org_id] += 1
            stats["sessions_created"] += 1

    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    user_profile_rows = [
        {
            "user_id": user_id,
            "organization_id": users[user_id]["organization_id"],
            "top_categories_json": json.dumps(
                [name for name, _ in user_category_counts[user_id].most_common(6)],
                ensure_ascii=False,
            ),
            "recent_ste_ids_json": json.dumps(
                list(user_recent_ste_ids[user_id]),
                ensure_ascii=False,
            ),
            "top_suppliers_json": json.dumps(
                [name for name, _ in user_supplier_counts[user_id].most_common(6)],
                ensure_ascii=False,
            ),
            "popular_queries_json": json.dumps(
                [query for query, _ in user_query_counts[user_id].most_common(8)],
                ensure_ascii=False,
            ),
            "updated_at": timestamp,
        }
        for user_id in sorted(users)
    ]
    org_profile_rows = [
        {
            "organization_id": organization_id,
            "top_categories_json": json.dumps(
                [name for name, _ in org_category_counts[organization_id].most_common(6)],
                ensure_ascii=False,
            ),
            "popular_ste_ids_json": json.dumps(
                [ste_id for ste_id, _ in org_popular_ste_counts[organization_id].most_common(8)],
                ensure_ascii=False,
            ),
            "updated_at": timestamp,
        }
        for organization_id in sorted(organizations)
    ]

    stats["users_created"] = len(users)
    stats["organizations_created"] = len(organizations)
    stats["purchase_rows"] = len(purchase_rows)
    stats["query_relevance_rows"] = len(query_relevance_rows)

    return (
        {
            "organizations": list(sorted(organizations.values(), key=lambda row: row["id"])),
            "users": list(sorted(users.values(), key=lambda row: row["id"])),
            "purchase_history": purchase_rows,
            "query_relevance": query_relevance_rows,
            "user_search_profiles": user_profile_rows,
            "org_search_profiles": org_profile_rows,
        },
        dict(stats),
    )


def main() -> None:
    args = parse_args()
    config = BuildConfig(
        contract_limit=args.contract_limit,
        max_organizations=args.max_organizations,
        max_contracts_per_org=args.max_contracts_per_org,
        candidate_limit=args.candidate_limit,
        visible_limit=args.visible_limit,
        query_term_limit=args.query_term_limit,
        min_query_terms=args.min_query_terms,
        min_match_score=args.min_match_score,
        max_samples_per_category=args.max_samples_per_category,
    )

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    state_dir = _resolve_state_dir(output_dir, args.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    ste_csv_path = _resolve_input_file(args.ste_csv, search_root=input_dir, pattern="СТЕ*.csv")
    contracts_csv_path = _resolve_input_file(
        args.contracts_csv,
        search_root=input_dir,
        pattern="Контракты*.csv",
    )
    print(
        f"[build_portal_dataset] input={input_dir} | ste={ste_csv_path.name} | contracts={contracts_csv_path.name}",
        flush=True,
    )
    print(f"[build_portal_dataset] output={output_dir}", flush=True)
    print(f"[build_portal_dataset] state={state_dir} | phase={args.phase}", flush=True)

    if args.phase in {"all", "catalog"}:
        (
            item_by_id,
            category_by_id,
            supplier_by_id,
            token_to_category_ids,
            category_samples,
            catalog_stats,
        ) = _build_sampled_catalog(
            ste_csv_path=ste_csv_path,
            max_samples_per_category=config.max_samples_per_category,
        )
        if not item_by_id:
            raise SystemExit("Sampled catalog is empty. Could not build ML dataset from STE source.")
        _save_catalog_snapshot(
            state_dir=state_dir,
            item_by_id=item_by_id,
            category_by_id=category_by_id,
            supplier_by_id=supplier_by_id,
            token_to_category_ids=token_to_category_ids,
            category_samples=category_samples,
            catalog_stats=catalog_stats,
        )
        print(
            f"[build_portal_dataset] catalog snapshot saved: {_catalog_snapshot_path(state_dir)}",
            flush=True,
        )
        if args.phase == "catalog":
            return
    else:
        (
            item_by_id,
            category_by_id,
            supplier_by_id,
            token_to_category_ids,
            category_samples,
            catalog_stats,
        ) = _load_catalog_snapshot(state_dir)
        print(
            f"[build_portal_dataset] catalog snapshot loaded: {_catalog_snapshot_path(state_dir)}",
            flush=True,
        )

    if args.phase in {"all", "buyers"}:
        selected_buyers, buyer_stats = _select_buyers(
            contracts_csv_path=contracts_csv_path,
            contract_limit=config.contract_limit,
            max_organizations=config.max_organizations,
        )
        _save_selected_buyers(
            state_dir=state_dir,
            selected_buyers=selected_buyers,
            buyer_stats=buyer_stats,
        )
        print(
            f"[build_portal_dataset] selected buyers saved: {_selected_buyers_path(state_dir)}",
            flush=True,
        )
        if args.phase == "buyers":
            return
    else:
        selected_buyers, buyer_stats = _load_selected_buyers(state_dir)
        print(
            f"[build_portal_dataset] selected buyers loaded: {_selected_buyers_path(state_dir)}",
            flush=True,
        )

    synonym_rows = _build_default_synonym_rows()
    spell_rows = _build_default_spell_rows()
    dataset_rows, dataset_stats = _build_dataset_rows(
        contracts_csv_path=contracts_csv_path,
        item_by_id=item_by_id,
        token_to_category_ids=token_to_category_ids,
        category_samples=category_samples,
        retrieval_builder=None,
        config=config,
        selected_buyers=selected_buyers,
    )
    if not dataset_rows["query_relevance"]:
        raise SystemExit("No training sessions were built from contracts. Try lowering filters or limits.")

    item_rows = list(sorted(item_by_id.values(), key=lambda row: row["id"]))
    category_rows = list(sorted(category_by_id.values(), key=lambda row: row["id"]))
    supplier_rows = list(sorted(supplier_by_id.values(), key=lambda row: row["id"]))

    _write_csv(
        output_dir / "ste_items.csv",
        item_rows,
        ["id", "title", "description", "category_id", "supplier_id", "attributes_json", "status", "updated_at"],
    )
    _write_csv(
        output_dir / "categories.csv",
        category_rows,
        ["id", "name", "parent_id"],
    )
    _write_csv(
        output_dir / "suppliers.csv",
        supplier_rows,
        ["id", "name"],
    )
    _write_csv(
        output_dir / "organizations.csv",
        dataset_rows["organizations"],
        ["id", "name"],
    )
    _write_csv(
        output_dir / "users.csv",
        dataset_rows["users"],
        ["id", "organization_id", "name", "role"],
    )
    _write_csv(
        output_dir / "purchase_history.csv",
        dataset_rows["purchase_history"],
        ["id", "user_id", "organization_id", "ste_id", "quantity", "price", "purchased_at"],
    )
    _write_csv(
        output_dir / "search_sessions.csv",
        [],
        ["id", "user_id", "organization_id", "query", "normalized_query", "created_at"],
    )
    _write_csv(
        output_dir / "search_events.csv",
        [],
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
    _write_csv(
        output_dir / "query_relevance.csv",
        dataset_rows["query_relevance"],
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
    _write_csv(
        output_dir / "user_search_profiles.csv",
        dataset_rows["user_search_profiles"],
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
    _write_csv(
        output_dir / "org_search_profiles.csv",
        dataset_rows["org_search_profiles"],
        [
            "organization_id",
            "top_categories_json",
            "popular_ste_ids_json",
            "updated_at",
        ],
    )
    _write_csv(
        output_dir / "synonyms.csv",
        synonym_rows,
        ["id", "term", "synonym", "weight", "source"],
    )
    _write_csv(
        output_dir / "spell_corrections.csv",
        spell_rows,
        ["id", "wrong_term", "correct_term", "source"],
    )

    stats_payload = {
        "input": {
            "input_dir": str(input_dir),
            "ste_csv_path": str(ste_csv_path),
            "contracts_csv_path": str(contracts_csv_path),
        },
        "output_dir": str(output_dir),
        "state_dir": str(state_dir),
        "config": {
            "phase": args.phase,
            "contract_limit": config.contract_limit,
            "max_organizations": config.max_organizations,
            "max_contracts_per_org": config.max_contracts_per_org,
            "candidate_limit": config.candidate_limit,
            "visible_limit": config.visible_limit,
            "query_term_limit": config.query_term_limit,
            "min_query_terms": config.min_query_terms,
            "min_match_score": config.min_match_score,
            "max_samples_per_category": config.max_samples_per_category,
        },
        "catalog": catalog_stats,
        "buyers": buyer_stats,
        "dataset": dataset_stats,
    }
    (output_dir / "dataset_stats.json").write_text(
        json.dumps(stats_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Portal ML dataset created.")
    print(f"- output: {output_dir}")
    print(f"- sampled_catalog_items: {catalog_stats['sampled_catalog_items']}")
    print(f"- sessions_created: {dataset_stats['sessions_created']}")
    print(f"- query_relevance_rows: {dataset_stats['query_relevance_rows']}")


if __name__ == "__main__":
    main()
