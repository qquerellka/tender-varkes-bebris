from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.search.normalizer import (
    TERM_NORMALIZATIONS,
    extract_normalized_tokens,
    extract_query_terms,
    lemmatize_query_terms,
    normalize_query,
)

SIZE_TOKENS = {
    "xs",
    "s",
    "m",
    "l",
    "xl",
    "xxl",
    "xxxl",
    "a0",
    "a1",
    "a2",
    "a3",
    "a4",
    "a5",
    "a6",
}

COLOR_TERMS = {
    "белый",
    "белая",
    "белое",
    "черный",
    "черная",
    "черное",
    "синий",
    "синяя",
    "синее",
    "голубой",
    "зеленый",
    "красный",
    "серый",
    "серебристый",
    "желтый",
    "оранжевый",
    "фиолетовый",
    "розовый",
    "прозрачный",
}

MATERIAL_TERMS = {
    "нитрил",
    "нитриловый",
    "нитриловые",
    "латекс",
    "латексный",
    "латексные",
    "винил",
    "виниловый",
    "виниловые",
    "бумажный",
    "бумажные",
    "пластик",
    "пластиковый",
    "пластиковые",
    "металл",
    "металлический",
    "металлические",
}

PACKAGE_TERMS = {
    "упаковка",
    "пачка",
    "комплект",
    "набор",
    "коробка",
    "рулон",
    "лист",
    "штука",
}

UNIT_TERMS = {
    "грамм",
    "килограмм",
    "литр",
    "миллилитр",
    "метр",
    "миллиметр",
    "сантиметр",
    "штука",
    "упаковка",
    "лист",
    "пачка",
}

GENERIC_LATIN_TERMS = {
    "api",
    "cpu",
    "gpu",
    "hdd",
    "hdmi",
    "ios",
    "it",
    "lan",
    "linux",
    "ram",
    "ssd",
    "usb",
    "wifi",
}

ALPHANUMERIC_TOKEN_PATTERN = re.compile(r"^(?=.*[a-zа-я])(?=.*\d)[a-zа-я0-9-]+$")
ATTACHED_MEASUREMENT_PATTERN = re.compile(r"^(?P<value>\d+(?:[.,]\d+)?)(?P<unit>[a-zа-я]+)$")
DIMENSION_TOKEN_PATTERN = re.compile(r"^\d+(?:[.,]\d+)?(?:х\d+(?:[.,]\d+)?){1,2}$")
PAPER_SIZE_PATTERN = re.compile(r"^a[0-6]$")
PURE_LATIN_PATTERN = re.compile(r"^[a-z]{2,}$")
SPEC_CODE_PATTERN = re.compile(r"^(?:гост|ту|iso|din|en|окпд2|окп|арт|артикул)[a-zа-я0-9-]*$")


@dataclass(slots=True)
class QuantityConstraint:
    raw_value: str
    value: str
    unit: str

    @property
    def normalized(self) -> str:
        return f"{self.value} {self.unit}".strip()


@dataclass(slots=True)
class SearchTextAnalysis:
    normalized_text: str
    token_sequence: list[str] = field(default_factory=list)
    text_terms: list[str] = field(default_factory=list)
    lemma_terms: list[str] = field(default_factory=list)
    brand_terms: list[str] = field(default_factory=list)
    model_terms: list[str] = field(default_factory=list)
    code_terms: list[str] = field(default_factory=list)
    numeric_terms: list[str] = field(default_factory=list)
    unit_terms: list[str] = field(default_factory=list)
    size_terms: list[str] = field(default_factory=list)
    package_terms: list[str] = field(default_factory=list)
    color_terms: list[str] = field(default_factory=list)
    material_terms: list[str] = field(default_factory=list)
    category_hints: list[str] = field(default_factory=list)
    attribute_terms: list[str] = field(default_factory=list)
    quantity_constraints: list[QuantityConstraint] = field(default_factory=list)
    phrase_queries: tuple[str, ...] = field(init=False)
    strict_terms: tuple[str, ...] = field(init=False)
    all_terms: tuple[str, ...] = field(init=False)
    token_set: frozenset[str] = field(init=False)
    text_term_set: frozenset[str] = field(init=False)
    lemma_term_set: frozenset[str] = field(init=False)
    brand_term_set: frozenset[str] = field(init=False)
    model_term_set: frozenset[str] = field(init=False)
    code_term_set: frozenset[str] = field(init=False)
    size_term_set: frozenset[str] = field(init=False)
    category_hint_set: frozenset[str] = field(init=False)
    attribute_term_set: frozenset[str] = field(init=False)
    all_term_set: frozenset[str] = field(init=False)

    def __post_init__(self) -> None:
        phrases = [self.normalized_text]
        category_phrase = " ".join(self.category_hints).strip()
        if category_phrase and category_phrase != self.normalized_text:
            phrases.append(category_phrase)
        self.phrase_queries = tuple(dict.fromkeys(item for item in phrases if item))

        strict_terms = [
            *self.brand_terms,
            *self.model_terms,
            *self.code_terms,
            *self.size_terms,
            *self.package_terms,
            *self.numeric_terms,
            *self.unit_terms,
        ]
        strict_terms.extend(constraint.normalized for constraint in self.quantity_constraints)
        self.strict_terms = tuple(dict.fromkeys(item for item in strict_terms if item))

        combined = [
            *self.text_terms,
            *self.lemma_terms,
            *self.brand_terms,
            *self.model_terms,
            *self.code_terms,
            *self.numeric_terms,
            *self.unit_terms,
            *self.size_terms,
            *self.package_terms,
            *self.color_terms,
            *self.material_terms,
            *self.category_hints,
            *self.attribute_terms,
        ]
        combined.extend(constraint.normalized for constraint in self.quantity_constraints)
        self.all_terms = tuple(dict.fromkeys(item for item in combined if item))
        self.token_set = frozenset(self.token_sequence)
        self.text_term_set = frozenset(self.text_terms)
        self.lemma_term_set = frozenset(self.lemma_terms)
        self.brand_term_set = frozenset(self.brand_terms)
        self.model_term_set = frozenset(self.model_terms)
        self.code_term_set = frozenset(self.code_terms)
        self.size_term_set = frozenset(self.size_terms)
        self.category_hint_set = frozenset(self.category_hints)
        self.attribute_term_set = frozenset(self.attribute_terms)
        self.all_term_set = frozenset(self.all_terms)

    @property
    def is_hard_query(self) -> bool:
        return bool(
            self.brand_terms
            or self.model_terms
            or self.code_terms
            or self.size_terms
            or self.quantity_constraints
            or len(self.numeric_terms) >= 2
        )


def analyze_search_text(value: str) -> SearchTextAnalysis:
    normalized_text = normalize_query(value)
    token_sequence = extract_normalized_tokens(normalized_text)
    text_terms = extract_query_terms(normalized_text)
    lemma_terms = lemmatize_query_terms(text_terms)
    quantity_constraints = _extract_quantity_constraints(token_sequence)

    numeric_terms = [token for token in token_sequence if _is_number_token(token)]
    unit_terms = _collect_unit_terms(token_sequence, quantity_constraints)
    size_terms = _collect_size_terms(token_sequence)
    package_terms = [token for token in text_terms if token in PACKAGE_TERMS]
    color_terms = [token for token in lemma_terms if token in COLOR_TERMS]
    material_terms = [token for token in lemma_terms if token in MATERIAL_TERMS]
    color_source_terms = _collect_source_terms(text_terms, COLOR_TERMS)
    material_source_terms = _collect_source_terms(text_terms, MATERIAL_TERMS)
    brand_terms = _collect_brand_terms(token_sequence)
    model_terms = _collect_model_terms(token_sequence)
    code_terms = _collect_code_terms(token_sequence)

    structured_terms = set(
        [
            *numeric_terms,
            *unit_terms,
            *size_terms,
            *package_terms,
            *color_terms,
            *material_terms,
            *brand_terms,
            *model_terms,
            *code_terms,
        ]
    )
    structured_terms.update(constraint.normalized for constraint in quantity_constraints)

    category_hints = [
        term
        for term in text_terms
        if term and term not in structured_terms
        and term not in color_source_terms
        and term not in material_source_terms
    ]

    attribute_terms = list(
        dict.fromkeys(
            [
                *brand_terms,
                *model_terms,
                *code_terms,
                *size_terms,
                *package_terms,
                *color_terms,
                *material_terms,
                *unit_terms,
            ]
        )
    )
    attribute_terms.extend(
        constraint.normalized
        for constraint in quantity_constraints
        if constraint.normalized not in attribute_terms
    )

    return SearchTextAnalysis(
        normalized_text=normalized_text,
        token_sequence=token_sequence,
        text_terms=text_terms,
        lemma_terms=lemma_terms,
        brand_terms=brand_terms,
        model_terms=model_terms,
        code_terms=code_terms,
        numeric_terms=list(dict.fromkeys(numeric_terms)),
        unit_terms=unit_terms,
        size_terms=size_terms,
        package_terms=package_terms,
        color_terms=color_terms,
        material_terms=material_terms,
        category_hints=list(dict.fromkeys(category_hints)),
        attribute_terms=list(dict.fromkeys(attribute_terms)),
        quantity_constraints=quantity_constraints,
    )


def _extract_quantity_constraints(tokens: list[str]) -> list[QuantityConstraint]:
    constraints: list[QuantityConstraint] = []
    seen: set[tuple[str, str]] = set()

    for index, token in enumerate(tokens):
        attached_match = ATTACHED_MEASUREMENT_PATTERN.fullmatch(token)
        if attached_match:
            normalized_unit = _normalize_unit(attached_match.group("unit"))
            if normalized_unit:
                key = (attached_match.group("value"), normalized_unit)
                if key not in seen:
                    seen.add(key)
                    constraints.append(
                        QuantityConstraint(
                            raw_value=token,
                            value=attached_match.group("value"),
                            unit=normalized_unit,
                        )
                    )
                continue

        if not _is_number_token(token):
            continue

        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        normalized_unit = _normalize_unit(next_token)
        if not normalized_unit:
            continue

        key = (token, normalized_unit)
        if key in seen:
            continue
        seen.add(key)
        constraints.append(
            QuantityConstraint(
                raw_value=f"{token} {next_token}".strip(),
                value=token,
                unit=normalized_unit,
            )
        )

    return constraints


def _collect_unit_terms(
    tokens: list[str],
    constraints: list[QuantityConstraint],
) -> list[str]:
    units = [
        normalized_unit
        for token in tokens
        if (normalized_unit := _normalize_unit(token)) is not None
    ]
    units.extend(constraint.unit for constraint in constraints)
    return list(dict.fromkeys(units))


def _collect_size_terms(tokens: list[str]) -> list[str]:
    sizes = [
        token
        for token in tokens
        if token in SIZE_TOKENS
        or PAPER_SIZE_PATTERN.fullmatch(token)
        or DIMENSION_TOKEN_PATTERN.fullmatch(token)
    ]
    return list(dict.fromkeys(sizes))


def _collect_brand_terms(tokens: list[str]) -> list[str]:
    brands = [
        token
        for token in tokens
        if PURE_LATIN_PATTERN.fullmatch(token)
        and token not in GENERIC_LATIN_TERMS
        and token not in SIZE_TOKENS
    ]
    return list(dict.fromkeys(brands))


def _collect_model_terms(tokens: list[str]) -> list[str]:
    models = [
        token
        for token in tokens
        if ALPHANUMERIC_TOKEN_PATTERN.fullmatch(token)
        and not PAPER_SIZE_PATTERN.fullmatch(token)
    ]
    return list(dict.fromkeys(models))


def _collect_code_terms(tokens: list[str]) -> list[str]:
    codes = [token for token in tokens if SPEC_CODE_PATTERN.fullmatch(token)]
    return list(dict.fromkeys(codes))


def _normalize_unit(token: str) -> str | None:
    if not token:
        return None

    normalized_token = TERM_NORMALIZATIONS.get(token, token)
    if normalized_token in UNIT_TERMS:
        return normalized_token
    return None


def _is_number_token(token: str) -> bool:
    if not token:
        return False
    return token.replace(",", ".", 1).replace(".", "", 1).isdigit()


def _collect_source_terms(terms: list[str], vocabulary: set[str]) -> list[str]:
    source_terms: list[str] = []
    for term in terms:
        if term in vocabulary:
            source_terms.append(term)
            continue
        if set(lemmatize_query_terms([term])) & vocabulary:
            source_terms.append(term)
    return list(dict.fromkeys(source_terms))
