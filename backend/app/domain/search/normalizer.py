import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

try:
    from pymorphy3 import MorphAnalyzer
except ImportError:  # pragma: no cover - dependency is optional at import time
    MorphAnalyzer = None


STOP_WORDS = {
    "в",
    "во",
    "для",
    "до",
    "и",
    "из",
    "или",
    "к",
    "на",
    "о",
    "об",
    "от",
    "по",
    "под",
    "при",
    "с",
    "со",
    "у",
    "товар",
    "товары",
}

LATIN_TO_CYRILLIC = str.maketrans(
    {
        "q": "й",
        "w": "ц",
        "e": "у",
        "r": "к",
        "t": "е",
        "y": "н",
        "u": "г",
        "i": "ш",
        "o": "щ",
        "p": "з",
        "[": "х",
        "]": "ъ",
        "a": "ф",
        "s": "ы",
        "d": "в",
        "f": "а",
        "g": "п",
        "h": "р",
        "j": "о",
        "k": "л",
        "l": "д",
        ";": "ж",
        "'": "э",
        "z": "я",
        "x": "ч",
        "c": "с",
        "v": "м",
        "b": "и",
        "n": "т",
        "m": "ь",
        ",": "б",
        ".": "ю",
        "`": "ё",
    }
)

SPELL_SIMILARITY_MAP = str.maketrans(
    {
        "ё": "е",
        "э": "е",
        "й": "и",
        "ъ": "ь",
        "щ": "ш",
        "ф": "в",
    }
)

TERM_NORMALIZATIONS = {
    "гм2": "грамм на квадратный метр",
    "гр": "грамм",
    "гр.": "грамм",
    "кг": "килограмм",
    "л": "литр",
    "л.": "литр",
    "м": "метр",
    "м.": "метр",
    "мл": "миллилитр",
    "мм": "миллиметр",
    "см": "сантиметр",
    "шт": "штука",
    "шт.": "штука",
    "уп": "упаковка",
    "уп.": "упаковка",
    "упак": "упаковка",
    "лист": "лист",
    "листа": "лист",
    "листов": "лист",
    "листы": "лист",
    "пач": "пачка",
    "пач.": "пачка",
    "пачка": "пачка",
    "пачки": "пачка",
    "пачек": "пачка",
}

TERM_EXPANSIONS = {
    "мфу": [
        "многофункциональное устройство",
        "принтер",
        "сканер",
        "копир",
    ],
    "пк": [
        "персональный компьютер",
        "компьютер",
    ],
    "ноут": ["ноутбук"],
    "оргтехника": [
        "офисная техника",
        "организационная техника",
    ],
    "канцтовары": [
        "канцелярские товары",
        "офисные принадлежности",
        "канцелярия",
    ],
    "канцелярия": [
        "канцтовары",
        "канцелярские товары",
        "офисные принадлежности",
    ],
    "канцтовар": [
        "канцтовары",
        "канцелярские товары",
    ],
    "хозтовары": ["хозяйственные товары"],
    "ибп": [
        "источник бесперебойного питания",
        "ups",
    ],
    "озу": [
        "оперативная память",
        "ram",
    ],
    "ссд": [
        "ssd",
        "твердотельный накопитель",
    ],
    "жк": ["жидкокристаллический"],
    "лкм": ["лакокрасочные материалы"],
    "гсм": ["горюче смазочные материалы"],
    "сиз": ["средства индивидуальной защиты"],
}
MAX_SEARCH_TOKEN_LENGTH = 64

PHRASE_NORMALIZATION_PATTERNS = (
    (re.compile(r"\bканц[\w-]*\s+товар[\w-]*\b"), "канцтовары"),
    (re.compile(r"\bканцелярск[\w-]*\s+товар[\w-]*\b"), "канцтовары"),
    (re.compile(r"\bорг[\w-]*\s+техник[\w-]*\b"), "оргтехника"),
    (re.compile(r"\bхоз[\w-]*\s+товар[\w-]*\b"), "хозтовары"),
    (re.compile(r"\bрабоч[\w-]*\s+станц[\w-]*\b"), "рабочая станция"),
    (re.compile(r"\bперсональн[\w-]*\s+компьютер[\w-]*\b"), "персональный компьютер"),
)

RUSSIAN_SUFFIX_REWRITES = (
    ("иями", "ия"),
    ("ями", "я"),
    ("ами", "а"),
    ("ого", "ый"),
    ("его", "ий"),
    ("ому", "ый"),
    ("ему", "ий"),
    ("ыми", "ый"),
    ("ими", "ий"),
    ("ых", "ый"),
    ("их", "ий"),
    ("ее", "ий"),
    ("ие", "ий"),
    ("ые", "ый"),
    ("ое", "ый"),
    ("ая", "ый"),
    ("яя", "ий"),
    ("ую", "ый"),
    ("юю", "ий"),
    ("ов", ""),
    ("ев", ""),
    ("ей", ""),
    ("ам", ""),
    ("ям", ""),
    ("ах", ""),
    ("ях", ""),
    ("ом", ""),
    ("ем", ""),
    ("ы", ""),
    ("а", ""),
    ("я", ""),
    ("е", ""),
    ("о", ""),
    ("у", ""),
    ("ю", ""),
)

PURE_LATIN_TOKEN_PATTERN = re.compile(r"^[a-z]+$")
PURE_CYRILLIC_TOKEN_PATTERN = re.compile(r"^[а-я]+$")
TOKEN_PATTERN = re.compile(r"[0-9a-zа-яё]+")
WHITESPACE_PATTERN = re.compile(r"\s+")
NON_SEARCH_CHARS_PATTERN = re.compile(r"[^0-9a-zа-яё./\s-]+")
LETTER_SEPARATOR_PATTERN = re.compile(r"(?<=[a-zа-яё])[-/](?=[a-zа-яё])")
DIMENSION_PATTERN = re.compile(r"(?<=\d)\s*[xх]\s*(?=\d)")
GRAMMAGE_PATTERN = re.compile(r"\bг\s*/\s*м(?:2|²)\b")

LATIN_VOWELS = set("aeiouy")
CYRILLIC_VOWELS = set("аеёиоуыэюя")
GENITIVE_TO_A_ENDINGS = set("гкхжчшщ")
LATIN_PRESERVE_TOKENS = {
    "amd",
    "api",
    "cpu",
    "dell",
    "epson",
    "gpu",
    "hdd",
    "hdmi",
    "hp",
    "intel",
    "ios",
    "it",
    "lan",
    "lenovo",
    "linux",
    "ram",
    "ssd",
    "usb",
    "wifi",
    "xerox",
}
CYRILLIC_ABBREVIATIONS = {
    "гсм",
    "жк",
    "ибп",
    "лкм",
    "мфу",
    "озу",
    "пк",
    "сиз",
    "ссд",
}


@dataclass(frozen=True, slots=True)
class SpellVocabularyIndex:
    tokens: frozenset[str]
    signature_buckets: dict[tuple[str, int], tuple[str, ...]]


def normalize_query(value: str) -> str:
    value = value.strip().lower().replace("ё", "е")
    value = GRAMMAGE_PATTERN.sub("гм2", value)
    value = DIMENSION_PATTERN.sub("х", value)
    value = LETTER_SEPARATOR_PATTERN.sub(" ", value)
    value = NON_SEARCH_CHARS_PATTERN.sub(" ", value)
    for pattern, replacement in PHRASE_NORMALIZATION_PATTERNS:
        value = pattern.sub(replacement, value)
    value = WHITESPACE_PATTERN.sub(" ", value)
    return value.strip()


def correct_query(value: str, corrections: dict[str, str] | None = None) -> str | None:
    corrected = value
    for wrong, right in sorted(
        (corrections or {}).items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        pattern = rf"(?<!\w){re.escape(normalize_query(wrong))}(?!\w)"
        corrected = re.sub(pattern, normalize_query(right), corrected)
    corrected = normalize_query(corrected)
    return corrected if corrected != value else None


def correct_query_fuzzy(
    value: str,
    vocabulary: Iterable[str] | SpellVocabularyIndex | None = None,
) -> str | None:
    normalized = normalize_query(value)
    spell_vocabulary_index = _ensure_spell_vocabulary_index(vocabulary)
    spell_vocabulary = spell_vocabulary_index.tokens
    corrected_tokens: list[str] = []
    changed = False

    for token in normalized.split():
        if (
            token in STOP_WORDS
            or token.isdigit()
            or len(token) < 4
            or token in spell_vocabulary
        ):
            corrected_tokens.append(token)
            continue

        replacement = _best_fuzzy_correction(token, spell_vocabulary_index)
        corrected_tokens.append(replacement or token)
        changed = changed or replacement is not None

    if not changed:
        return None

    corrected = normalize_query(" ".join(corrected_tokens))
    return corrected if corrected != normalized else None


def expand_fuzzy_term_variants(
    terms: list[str],
    vocabulary: Iterable[str] | SpellVocabularyIndex | None = None,
    *,
    limit_per_term: int = 2,
) -> list[str]:
    spell_vocabulary_index = _ensure_spell_vocabulary_index(vocabulary)
    spell_vocabulary = spell_vocabulary_index.tokens
    expanded: list[str] = []

    for value in terms:
        for token in extract_query_terms(value):
            if (
                token in STOP_WORDS
                or token.isdigit()
                or len(token) < 4
                or token in spell_vocabulary
            ):
                continue

            for candidate in _select_fuzzy_variants(
                token,
                spell_vocabulary_index,
                limit=limit_per_term,
            ):
                _append_variant(expanded, candidate)

    return list(dict.fromkeys(expanded))


def correct_keyboard_layout(value: str) -> str | None:
    normalized = normalize_query(value)
    corrected_tokens: list[str] = []
    changed = False

    for token in normalized.split():
        if _looks_like_keyboard_layout_mistake(token):
            corrected = token.translate(LATIN_TO_CYRILLIC)
            corrected_tokens.append(corrected)
            changed = changed or corrected != token
            continue
        corrected_tokens.append(token)

    if not changed:
        return None

    corrected_value = normalize_query(" ".join(corrected_tokens))
    return corrected_value if corrected_value != normalized else None


def extract_query_terms(value: str, *, deduplicate: bool = True) -> list[str]:
    terms: list[str] = []

    for token in normalize_query(value).split():
        normalized_token = TERM_NORMALIZATIONS.get(token, token)
        if normalized_token in STOP_WORDS:
            continue
        if len(normalized_token) == 1 and not normalized_token.isdigit():
            continue
        if len(normalized_token) > MAX_SEARCH_TOKEN_LENGTH and not normalized_token.isdigit():
            continue
        terms.append(normalized_token)

    if not deduplicate:
        return terms
    return list(dict.fromkeys(terms))


def extract_normalized_tokens(
    value: str,
    *,
    deduplicate: bool = False,
) -> list[str]:
    tokens = [
        token
        for token in normalize_query(value).split()
        if token and (len(token) <= MAX_SEARCH_TOKEN_LENGTH or token.isdigit())
    ]
    if not deduplicate:
        return tokens
    return list(dict.fromkeys(tokens))


def lemmatize_query_terms(
    values: Iterable[str],
    *,
    deduplicate: bool = True,
) -> list[str]:
    lemmas: list[str] = []

    for value in values:
        normalized = normalize_query(str(value))
        if not normalized:
            continue

        source_terms = extract_query_terms(normalized, deduplicate=False)
        if not source_terms:
            source_terms = [TERM_NORMALIZATIONS.get(normalized, normalized)]

        for term in source_terms:
            lemma = _lemmatize_russian_term(term)
            if lemma is None:
                fallback_variants = _expand_russian_fallback_variants(term)
                lemma = next(
                    (candidate for candidate in fallback_variants if candidate and candidate != term),
                    term,
                )

            if len(lemma) == 1 and not lemma.isdigit():
                continue
            lemmas.append(lemma)

    if not deduplicate:
        return lemmas
    return list(dict.fromkeys(lemmas))


def expand_term_variants(terms: list[str]) -> list[str]:
    expanded: list[str] = []

    for term in terms:
        if not term:
            continue

        for variant in _expand_single_term(term):
            _append_variant(expanded, variant)
            if " " not in variant:
                continue
            for part in extract_query_terms(variant):
                for part_variant in _expand_single_term(part):
                    _append_variant(expanded, part_variant)

    return list(dict.fromkeys(item for item in expanded if len(item) >= 2 or item.isdigit()))


def _append_variant(target: list[str], value: str) -> None:
    if len(value) == 1 and not value.isdigit():
        return
    target.append(value)


def _expand_single_term(term: str) -> list[str]:
    variants = [term]
    variants.extend(TERM_EXPANSIONS.get(term, []))

    lemma = _lemmatize_russian_term(term)
    if lemma is not None:
        variants.append(lemma)
        variants.extend(TERM_EXPANSIONS.get(lemma, []))
    else:
        variants.extend(_expand_russian_fallback_variants(term))

    return list(dict.fromkeys(variant for variant in variants if variant))


@lru_cache(maxsize=1)
def _get_morph_analyzer() -> Any | None:
    if MorphAnalyzer is None:
        return None
    try:
        return MorphAnalyzer()
    except Exception:
        return None


@lru_cache(maxsize=200_000)
def _lemmatize_russian_term(term: str) -> str | None:
    if term in CYRILLIC_ABBREVIATIONS:
        return None
    if not PURE_CYRILLIC_TOKEN_PATTERN.fullmatch(term):
        return None
    if len(term) > MAX_SEARCH_TOKEN_LENGTH:
        return None

    analyzer = _get_morph_analyzer()
    if analyzer is None:
        return None

    try:
        parsed = analyzer.parse(term)
    except Exception:
        return None

    if not parsed:
        return None

    lemma = normalize_query(parsed[0].normal_form)
    if lemma == term or not _looks_like_russian_term(lemma):
        return None
    return lemma


@lru_cache(maxsize=200_000)
def _expand_russian_fallback_variants(term: str) -> list[str]:
    if not PURE_CYRILLIC_TOKEN_PATTERN.fullmatch(term):
        return []
    if len(term) > MAX_SEARCH_TOKEN_LENGTH:
        return []

    variants: list[str] = []

    if term.endswith("и") and len(term) >= 5:
        stem = term[:-1]
        variants.append(stem)
        if stem and stem[-1] in GENITIVE_TO_A_ENDINGS:
            variants.append(f"{stem}а")

    for suffix, replacement in RUSSIAN_SUFFIX_REWRITES:
        if not term.endswith(suffix):
            continue
        stem = term[: -len(suffix)]
        if len(stem) < 3:
            continue
        candidate = f"{stem}{replacement}"
        if _looks_like_russian_term(candidate):
            variants.append(candidate)
        if len(stem) >= 4:
            variants.append(stem)
        break

    return list(dict.fromkeys(variant for variant in variants if variant != term))


def _build_spell_vocabulary(vocabulary: Iterable[str] | None) -> set[str]:
    normalized_vocabulary = {
        token
        for value in (vocabulary or [])
        for token in TOKEN_PATTERN.findall(normalize_query(str(value)))
        if len(token) >= 3 and not token.isdigit()
    }

    for token in TERM_NORMALIZATIONS:
        if len(token) >= 3:
            normalized_vocabulary.add(token)
    for value in TERM_NORMALIZATIONS.values():
        normalized_vocabulary.update(
            token for token in extract_query_terms(value) if len(token) >= 3
        )

    for term, variants in TERM_EXPANSIONS.items():
        normalized_vocabulary.add(term)
        for variant in variants:
            normalized_vocabulary.update(
                token for token in extract_query_terms(variant) if len(token) >= 3
            )

    return normalized_vocabulary


def build_spell_vocabulary_index(
    vocabulary: Iterable[str] | SpellVocabularyIndex | None,
) -> SpellVocabularyIndex:
    if isinstance(vocabulary, SpellVocabularyIndex):
        return vocabulary

    normalized_vocabulary = _build_spell_vocabulary(vocabulary)
    signature_buckets: dict[tuple[str, int], list[str]] = {}

    for token in normalized_vocabulary:
        signature = _spell_signature(token)
        if not signature:
            continue

        signature_length = len(signature)
        prefixes = {signature[:1]}
        if signature_length >= 2:
            prefixes.add(signature[:2])

        for prefix in prefixes:
            signature_buckets.setdefault((prefix, signature_length), []).append(token)

    return SpellVocabularyIndex(
        tokens=frozenset(normalized_vocabulary),
        signature_buckets={
            key: tuple(sorted(values))
            for key, values in signature_buckets.items()
        },
    )


def _ensure_spell_vocabulary_index(
    vocabulary: Iterable[str] | SpellVocabularyIndex | None,
) -> SpellVocabularyIndex:
    return build_spell_vocabulary_index(vocabulary)


def _best_fuzzy_correction(
    token: str,
    vocabulary: SpellVocabularyIndex,
) -> str | None:
    candidates = _rank_fuzzy_candidates(token, vocabulary)
    if not candidates:
        return None

    best_distance, best_prefix_penalty, best_len_delta, best_candidate = candidates[0]
    runner_up_distance = candidates[1][0] if len(candidates) > 1 else best_distance + 2
    runner_up_prefix_penalty = candidates[1][1] if len(candidates) > 1 else 0

    if (
        len(candidates) > 1
        and best_distance == runner_up_distance
        and best_prefix_penalty == runner_up_prefix_penalty
        and best_len_delta == candidates[1][2]
    ):
        return None
    allowed_distance = _max_edit_distance(_spell_signature(token))
    if best_distance == allowed_distance and runner_up_distance - best_distance <= 0:
        return None
    return best_candidate


def _select_fuzzy_variants(
    token: str,
    vocabulary: SpellVocabularyIndex,
    *,
    limit: int,
) -> list[str]:
    ranked_candidates = _rank_fuzzy_candidates(token, vocabulary)
    if not ranked_candidates:
        return []

    best_distance = ranked_candidates[0][0]
    selected: list[str] = []

    for distance, prefix_penalty, _, candidate in ranked_candidates:
        shared_prefix = -prefix_penalty
        if shared_prefix == 0 and distance > 1:
            continue
        if distance - best_distance > 1:
            break
        if candidate in selected:
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break

    return selected


def _rank_fuzzy_candidates(
    token: str,
    vocabulary: SpellVocabularyIndex,
) -> list[tuple[int, int, int, str]]:
    token_signature = _spell_signature(token)
    allowed_distance = _max_edit_distance(token_signature)
    candidates: list[tuple[int, int, int, str]] = []

    min_length = max(3, len(token_signature) - allowed_distance)
    max_length = len(token_signature) + allowed_distance
    candidate_pool = _lookup_fuzzy_candidate_pool(
        token_signature=token_signature,
        vocabulary=vocabulary,
        min_length=min_length,
        max_length=max_length,
    )

    for candidate in candidate_pool:
        if candidate == token:
            continue
        if abs(len(candidate) - len(token)) > allowed_distance:
            continue

        candidate_signature = _spell_signature(candidate)
        if candidate_signature[:1] != token_signature[:1]:
            continue

        signature_distance = _levenshtein_distance(
            token_signature,
            candidate_signature,
            max_distance=allowed_distance,
        )
        if signature_distance is None:
            continue

        raw_distance = _levenshtein_distance(
            token,
            candidate,
            max_distance=allowed_distance + 1,
        )
        if raw_distance is None:
            raw_distance = allowed_distance + 1

        effective_distance = min(signature_distance, raw_distance)
        if effective_distance > allowed_distance:
            continue

        shared_prefix = _shared_prefix_len(token_signature, candidate_signature)
        if shared_prefix == 0 and effective_distance > 1:
            continue

        candidates.append(
            (
                effective_distance,
                -shared_prefix,
                abs(len(candidate) - len(token)),
                candidate,
            )
        )

    candidates.sort()
    return candidates


def _lookup_fuzzy_candidate_pool(
    *,
    token_signature: str,
    vocabulary: SpellVocabularyIndex,
    min_length: int,
    max_length: int,
) -> tuple[str, ...]:
    if not token_signature:
        return ()

    for prefix_length in (2, 1):
        if len(token_signature) < prefix_length:
            continue

        prefix = token_signature[:prefix_length]
        candidates: list[str] = []
        seen: set[str] = set()

        for candidate_length in range(min_length, max_length + 1):
            for candidate in vocabulary.signature_buckets.get((prefix, candidate_length), ()):
                if candidate in seen:
                    continue
                seen.add(candidate)
                candidates.append(candidate)

        if candidates:
            return tuple(candidates)

    return ()


def _spell_signature(value: str) -> str:
    return normalize_query(value).translate(SPELL_SIMILARITY_MAP)


def _max_edit_distance(token: str) -> int:
    length = len(token)
    if length <= 4:
        return 1
    if length <= 8:
        return 2
    return 3


def _levenshtein_distance(
    left: str,
    right: str,
    *,
    max_distance: int,
) -> int | None:
    if left == right:
        return 0

    left_len = len(left)
    right_len = len(right)
    if abs(left_len - right_len) > max_distance:
        return None

    if left_len > right_len:
        left, right = right, left
        left_len, right_len = right_len, left_len

    previous_row = list(range(right_len + 1))
    for left_index, left_char in enumerate(left, start=1):
        current_row = [left_index]
        row_min = left_index

        start = max(1, left_index - max_distance)
        end = min(right_len, left_index + max_distance)

        if start > 1:
            current_row.extend([max_distance + 1] * (start - 1))

        for right_index in range(start, end + 1):
            cost = 0 if left_char == right[right_index - 1] else 1
            insert_cost = current_row[-1] + 1
            delete_cost = previous_row[right_index] + 1
            replace_cost = previous_row[right_index - 1] + cost
            value = min(insert_cost, delete_cost, replace_cost)
            current_row.append(value)
            row_min = min(row_min, value)

        if end < right_len:
            current_row.extend([max_distance + 1] * (right_len - end))

        if row_min > max_distance:
            return None

        previous_row = current_row

    distance = previous_row[right_len]
    return distance if distance <= max_distance else None


def _shared_prefix_len(left: str, right: str) -> int:
    size = 0
    for left_char, right_char in zip(left, right, strict=False):
        if left_char != right_char:
            break
        size += 1
    return size


def _looks_like_keyboard_layout_mistake(token: str) -> bool:
    if not PURE_LATIN_TOKEN_PATTERN.fullmatch(token):
        return False
    if len(token) < 4:
        return False
    if token in LATIN_PRESERVE_TOKENS:
        return False

    vowel_count = sum(char in LATIN_VOWELS for char in token)
    vowel_ratio = vowel_count / max(len(token), 1)
    return vowel_ratio < 0.25 or _max_latin_consonant_run(token) >= 4


def _max_latin_consonant_run(token: str) -> int:
    best = 0
    current = 0
    for char in token:
        if char in LATIN_VOWELS:
            current = 0
            continue
        current += 1
        best = max(best, current)
    return best


def _looks_like_russian_term(value: str) -> bool:
    if not value or not PURE_CYRILLIC_TOKEN_PATTERN.fullmatch(value):
        return False
    return any(char in CYRILLIC_VOWELS for char in value)
