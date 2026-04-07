from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.db.models import (
    CategoryModel,
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


@dataclass(frozen=True)
class TableSpec:
    filename: str
    model: type
    json_defaults: dict[str, Any]
    datetime_columns: tuple[str, ...]
    nullable_columns: tuple[str, ...]


TABLE_SPECS: tuple[TableSpec, ...] = (
    TableSpec(
        filename="organizations.csv",
        model=OrganizationModel,
        json_defaults={},
        datetime_columns=(),
        nullable_columns=(),
    ),
    TableSpec(
        filename="categories.csv",
        model=CategoryModel,
        json_defaults={},
        datetime_columns=(),
        nullable_columns=("parent_id",),
    ),
    TableSpec(
        filename="suppliers.csv",
        model=SupplierModel,
        json_defaults={},
        datetime_columns=(),
        nullable_columns=(),
    ),
    TableSpec(
        filename="users.csv",
        model=UserModel,
        json_defaults={},
        datetime_columns=(),
        nullable_columns=(),
    ),
    TableSpec(
        filename="ste_items.csv",
        model=STEItemModel,
        json_defaults={"attributes_json": {}},
        datetime_columns=("updated_at",),
        nullable_columns=(),
    ),
    TableSpec(
        filename="synonyms.csv",
        model=SynonymModel,
        json_defaults={},
        datetime_columns=(),
        nullable_columns=(),
    ),
    TableSpec(
        filename="spell_corrections.csv",
        model=SpellCorrectionModel,
        json_defaults={},
        datetime_columns=(),
        nullable_columns=(),
    ),
    TableSpec(
        filename="purchase_history.csv",
        model=PurchaseHistoryModel,
        json_defaults={},
        datetime_columns=("purchased_at",),
        nullable_columns=(),
    ),
    TableSpec(
        filename="search_sessions.csv",
        model=SearchSessionModel,
        json_defaults={},
        datetime_columns=("created_at",),
        nullable_columns=(),
    ),
    TableSpec(
        filename="search_events.csv",
        model=SearchEventModel,
        json_defaults={"payload_json": {}},
        datetime_columns=("created_at",),
        nullable_columns=("ste_id",),
    ),
    TableSpec(
        filename="user_search_profiles.csv",
        model=UserSearchProfileModel,
        json_defaults={
            "top_categories_json": [],
            "recent_ste_ids_json": [],
            "top_suppliers_json": [],
            "popular_queries_json": [],
        },
        datetime_columns=("updated_at",),
        nullable_columns=(),
    ),
    TableSpec(
        filename="org_search_profiles.csv",
        model=OrgSearchProfileModel,
        json_defaults={
            "top_categories_json": [],
            "popular_ste_ids_json": [],
        },
        datetime_columns=("updated_at",),
        nullable_columns=(),
    ),
)

ISO_FRACTION_RE = re.compile(r"(\.\d{6})\d+(?=(?:[+-]\d{2}:\d{2})?$)")

CATEGORY_TRANSLATIONS = {
    "Transport": "Транспорт",
    "IT and Equipment": "ИТ и оборудование",
    "Services": "Услуги",
    "Office and Supplies": "Офис и снабжение",
}

ROLE_TRANSLATIONS = {
    "manager": "менеджер",
    "customer": "заказчик",
    "analyst": "аналитик",
}

SUPPLIER_TOKEN_TRANSLATIONS = {
    "ao": "АО",
    "ooo": "ООО",
    "zao": "ЗАО",
    "ip": "ИП",
    "astra": "Астра",
    "city": "Сити",
    "infra": "Инфра",
    "metro": "Метро",
    "network": "Сеть",
    "nova": "Нова",
    "service": "Сервис",
    "smart": "Смарт",
    "solutions": "Решения",
    "supply": "Снабжение",
    "systems": "Системы",
    "trade": "Трейд",
    "transit": "Транзит",
    "urban": "Урбан",
    "vector": "Вектор",
    "group": "Группа",
    "logistics": "Логистика",
}

TEXT_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("municipal organization", "муниципальная организация"),
    ("it and equipment", "ИТ и оборудование"),
    ("office and supplies", "Офис и снабжение"),
    ("product built around term", "предложение сформировано вокруг термина"),
    ("transport", "транспорт"),
    ("services", "услуги"),
    ("dlya ofisov", "для офисов"),
    ("dlya municipalnyh nuzhd", "для муниципальных нужд"),
    ("dlya infrastruktury", "для инфраструктуры"),
    ("dlya zakupok", "для закупок"),
    ("portal postavshikov", "портал поставщиков"),
    ("service desk", "сервис-деск"),
    ("it support", "ИТ-поддержка"),
    ("cleaning service", "клининговая услуга"),
    ("office supplies", "офисные товары"),
    ("transportnaya logistika", "транспортная логистика"),
    ("passazhirskie perevozki", "пассажирские перевозки"),
    ("passazhirskiy transport", "пассажирский транспорт"),
    ("servernoe oborudovanie", "серверное оборудование"),
    ("mobilnaya rabochaya stanciya", "мобильная рабочая станция"),
    ("rabochaya stanciya", "рабочая станция"),
    ("setevoy kommutator", "сетевой коммутатор"),
    ("setevoe oborudovanie", "сетевое оборудование"),
    ("uborka pomescheniy", "уборка помещений"),
    ("arenda transporta", "аренда транспорта"),
    ("tekhnicheskoe obsluzhivanie", "техническое обслуживание"),
    ("kompleksnaya postavka", "комплексная поставка"),
    ("passazhirskiy", "пассажирский"),
    ("postavka", "поставка"),
    ("arenda", "аренда"),
    ("usluga", "услуга"),
    ("obsluzhvaniye", "обслуживание"),
    ("obsluzhivanie", "обслуживание"),
    ("tehpodderzka", "техподдержка"),
    ("tehpodderzhka", "техподдержка"),
    ("soprovozhdenie", "сопровождение"),
    ("autsorsing", "аутсорсинг"),
    ("ofisnaya mebel", "офисная мебель"),
    ("kanctovri", "канцтовары"),
    ("kanctovary", "канцтовары"),
    ("katridzh", "картридж"),
    ("kartridzh", "картридж"),
    ("mikroaftobus", "микроавтобус"),
    ("mikroavtobus", "микроавтобус"),
    ("komutator", "коммутатор"),
    ("kommutator", "коммутатор"),
    ("logstika", "логистика"),
    ("logistika", "логистика"),
    ("noutbukk", "ноутбук"),
    ("noutbuk", "ноутбук"),
    ("printer", "принтер"),
    ("server", "сервер"),
    ("bumaga", "бумага"),
    ("paper", "бумага"),
    ("toner", "тонер"),
    ("stationery", "канцтовары"),
    ("minibus", "микроавтобус"),
    ("switch", "коммутатор"),
    ("compute node", "вычислительный узел"),
    ("ekspluataciya", "эксплуатация"),
    ("servis", "сервис"),
    ("klinng", "клининг"),
    ("klining", "клининг"),
    ("aftobus", "автобус"),
    ("avtobus", "автобус"),
    ("serer", "сервер"),
    ("perevozki", "перевозки"),
    ("s dostavkoy", "с доставкой"),
    ("pod klyuch", "под ключ"),
    ("dlya", "для"),
    ("ofisov", "офисов"),
    ("municipal", "для муниципальных нужд"),
    ("moskva", "в москве"),
    ("category", "категория"),
    ("user", "пользователь"),
    ("fleet_support", "поддержка автопарка"),
    ("maintenance", "обслуживание"),
    ("monthly", "ежемесячное обслуживание"),
    ("charter", "чартер"),
    ("office", "офис"),
    ("tower", "башенный"),
    ("it", "ИТ"),
    ("supply", "поставка"),
)


def _preserve_initial_case(original: str, translated: str) -> str:
    if original[:1].isupper() and translated:
        return translated[:1].upper() + translated[1:]
    return translated


def _replace_case_insensitive(text: str, source: str, target: str) -> str:
    pattern = re.compile(rf"(?<!\w){re.escape(source)}(?!\w)", flags=re.IGNORECASE)
    return pattern.sub(target, text)


def _translate_text(value: str) -> str:
    translated = value
    for source, target in TEXT_REPLACEMENTS:
        translated = _replace_case_insensitive(translated, source, target)

    translated = re.sub(r"\s+", " ", translated).strip()
    return _preserve_initial_case(value, translated)


def _translate_supplier_name(value: str) -> str:
    translated_tokens: list[str] = []
    for token in value.split():
        match = re.fullmatch(r"([A-Za-z]+)(\d+)?", token)
        if not match:
            translated_tokens.append(_translate_text(token))
            continue

        base, suffix = match.groups()
        translated_base = SUPPLIER_TOKEN_TRANSLATIONS.get(base.lower(), base)
        translated_tokens.append(f"{translated_base}{suffix or ''}")

    return " ".join(translated_tokens)


def _translate_list(values: list[Any], translator) -> list[Any]:
    return [translator(value) if isinstance(value, str) else value for value in values]


def _translate_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    translated: dict[str, Any] = {}
    for key, value in attributes.items():
        translated[key] = _translate_text(value) if isinstance(value, str) else value
    return translated


def _translate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    translated: dict[str, Any] = {}
    for key, value in payload.items():
        translated[key] = _translate_text(value) if isinstance(value, str) else value
    return translated


def _localize_row(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    localized = dict(row)

    if table_name == "organizations":
        localized["name"] = _translate_text(localized["name"])
    elif table_name == "users":
        localized["name"] = _translate_text(localized["name"])
        localized["role"] = ROLE_TRANSLATIONS.get(localized["role"], localized["role"])
    elif table_name == "categories":
        localized["name"] = CATEGORY_TRANSLATIONS.get(localized["name"], localized["name"])
    elif table_name == "suppliers":
        localized["name"] = _translate_supplier_name(localized["name"])
    elif table_name == "ste_items":
        localized["title"] = _translate_text(localized["title"])
        localized["description"] = _translate_text(localized["description"])
        localized["attributes_json"] = _translate_attributes(localized["attributes_json"])
    elif table_name == "synonyms":
        localized["term"] = _translate_text(localized["term"]).lower()
        localized["synonym"] = _translate_text(localized["synonym"]).lower()
    elif table_name == "spell_corrections":
        localized["wrong_term"] = _translate_text(localized["wrong_term"]).lower()
        localized["correct_term"] = _translate_text(localized["correct_term"]).lower()
    elif table_name == "search_sessions":
        localized["query"] = _translate_text(localized["query"]).lower()
        localized["normalized_query"] = _translate_text(localized["normalized_query"]).lower()
    elif table_name == "search_events":
        localized["payload_json"] = _translate_payload(localized["payload_json"])
    elif table_name == "user_search_profiles":
        localized["top_categories_json"] = _translate_list(
            localized["top_categories_json"], lambda value: CATEGORY_TRANSLATIONS.get(value, value)
        )
        localized["top_suppliers_json"] = _translate_list(
            localized["top_suppliers_json"], _translate_supplier_name
        )
        localized["popular_queries_json"] = _translate_list(
            localized["popular_queries_json"], lambda value: _translate_text(value).lower()
        )
    elif table_name == "org_search_profiles":
        localized["top_categories_json"] = _translate_list(
            localized["top_categories_json"], lambda value: CATEGORY_TRANSLATIONS.get(value, value)
        )

    return localized


def _parse_iso_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    value = ISO_FRACTION_RE.sub(r"\1", value)
    return datetime.fromisoformat(value)


def _parse_row(raw: dict[str, str], spec: TableSpec) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in raw.items():
        value = value.strip() if isinstance(value, str) else value

        if key in spec.nullable_columns and value == "":
            parsed[key] = None
            continue

        if key in spec.json_defaults:
            if value == "":
                parsed[key] = spec.json_defaults[key]
            else:
                parsed[key] = json.loads(value)
            continue

        if key in spec.datetime_columns:
            parsed[key] = _parse_iso_datetime(value)
            continue

        parsed[key] = value
    return parsed


def _read_csv_rows(path: Path, spec: TableSpec) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [_localize_row(spec.model.__tablename__, _parse_row(row, spec)) for row in reader]


def _truncate_all(session: Session) -> None:
    table_names = ", ".join(spec.model.__tablename__ for spec in TABLE_SPECS)
    try:
        session.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    except Exception:
        session.rollback()
        for spec in reversed(TABLE_SPECS):
            session.execute(delete(spec.model))


def import_synthetic_dataset(
    session: Session,
    data_dir: Path,
    truncate: bool = True,
) -> dict[str, int]:
    if not data_dir.exists():
        raise FileNotFoundError(f"Synthetic data directory does not exist: {data_dir}")

    stats: dict[str, int] = {}
    if truncate:
        _truncate_all(session)

    try:
        for spec in TABLE_SPECS:
            source = data_dir / spec.filename
            if not source.exists():
                raise FileNotFoundError(f"Required file not found: {source}")

            rows = _read_csv_rows(source, spec)
            if rows:
                session.bulk_insert_mappings(spec.model, rows)
            stats[spec.model.__tablename__] = len(rows)
        session.commit()
    except Exception:
        session.rollback()
        raise

    return stats
