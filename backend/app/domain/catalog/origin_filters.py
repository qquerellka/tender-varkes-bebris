from __future__ import annotations

import re

SPACE_RE = re.compile(r"\s+")

_ORIGIN_KEY_PREFIXES = (
    "страна производства",
    "страна производитель",
    "страна производителя",
    "страна происхождения",
    "страна происхождения товара",
    "страна происхождения сырья",
    "страна изготовления",
    "страна изготовитель",
    "страна изготовления",
    "страна производитель.",
    "страна-производитель",
    "страна -производитель",
    "страна происхождения и производства",
)
_ORIGIN_KEY_EXACT = {
    "страна",
    "страна (регион)",
    "регион",
    "регион производства",
}
_DOMESTIC_VALUE_HINTS = (
    "росси",
    "российск",
    "рф",
)


def normalize_origin_key(value: str) -> str:
    normalized = value.replace("\u00a0", " ").replace("\t", " ").strip(" :.-").lower()
    return SPACE_RE.sub(" ", normalized)


def normalize_origin_value(value: str) -> str:
    normalized = value.replace("\u00a0", " ").strip(" :.-")
    return SPACE_RE.sub(" ", normalized)


def is_origin_key(key: str) -> bool:
    normalized = normalize_origin_key(key)
    if normalized in _ORIGIN_KEY_EXACT:
        return True
    return normalized.startswith(_ORIGIN_KEY_PREFIXES)


def extract_origin_values(attributes: dict[str, str] | None) -> list[str]:
    if not isinstance(attributes, dict):
        return []

    values: list[str] = []
    seen: set[str] = set()
    for key, raw_value in attributes.items():
        if not is_origin_key(str(key)):
            continue
        value = normalize_origin_value(str(raw_value))
        if not value:
            continue
        normalized_key = value.lower()
        if normalized_key in seen:
            continue
        seen.add(normalized_key)
        values.append(value)
    return values


def is_domestic_origin_value(value: str) -> bool:
    normalized = normalize_origin_value(value).lower()
    return any(hint in normalized for hint in _DOMESTIC_VALUE_HINTS)


def matches_origin_filters(
    attributes: dict[str, str] | None,
    *,
    domestic_only: bool = False,
    origin_value: str | None = None,
) -> bool:
    if not domestic_only and not origin_value:
        return True

    values = extract_origin_values(attributes)
    if not values:
        return False

    if domestic_only and not any(is_domestic_origin_value(value) for value in values):
        return False

    if origin_value:
        selected = normalize_origin_value(origin_value).lower()
        if selected and all(normalize_origin_value(value).lower() != selected for value in values):
            return False

    return True
