# Контракт Интеграции С ML

Этот документ описывает актуальную границу между backend search pipeline и ML reranker.

## Цель

Backend остается orchestrator-ом поиска.

ML service должен улучшать:

- final reranking
- semantic relevance
- порядок внутри уже найденного candidate set

ML service не должен заменять:

- catalog storage
- search API contracts
- spell correction
- synonyms
- search sessions
- events
- candidate generation
- fallback ranking

Семантика пользовательских событий и таблиц telemetry описана отдельно в:
- [TELEMETRY_SPEC.md](/home/qquerell/programming/frontend-template/my-app/backend/TELEMETRY_SPEC.md)
- [TELEMETRY_EVENT_DICTIONARY.md](/home/qquerell/programming/frontend-template/my-app/backend/TELEMETRY_EVENT_DICTIONARY.md)
- [TELEMETRY_QA_CHECKLIST.md](/home/qquerell/programming/frontend-template/my-app/backend/TELEMETRY_QA_CHECKLIST.md)

Примеры экспортируемых данных для ML handoff:
- [examples/search_events.sample.jsonl](/home/qquerell/programming/frontend-template/my-app/backend/examples/search_events.sample.jsonl)
- [examples/search_impressions.sample.csv](/home/qquerell/programming/frontend-template/my-app/backend/examples/search_impressions.sample.csv)
- [examples/user_item_features.sample.csv](/home/qquerell/programming/frontend-template/my-app/backend/examples/user_item_features.sample.csv)

Для быстрой ручной проверки живой telemetry без SQL смотри готовые `curl`-примеры в [TELEMETRY_QA_CHECKLIST.md](/home/qquerell/programming/frontend-template/my-app/backend/TELEMETRY_QA_CHECKLIST.md).

## Текущий Search Pipeline

Сейчас backend делает следующие шаги:

1. Принимает search request от frontend.
2. Нормализует запрос.
3. Применяет dictionary spell correction из `spell_corrections`.
4. Применяет fuzzy spell correction по edit distance поверх vocabulary каталога.
5. Исправляет неправильную раскладку клавиатуры.
6. Извлекает поисковые термы.
7. Лемматизирует русские термы через `pymorphy3`.
8. Расширяет запрос доменными alias-ами.
9. Подмешивает синонимы из `synonyms`.
10. Формирует retrieval-каналы:
    - `BM25`
    - `trigram similarity`
    - `synonym-expanded BM25`
    - `semantic vector recall` на `BAAI/bge-m3` с fallback на TF-IDF/SVD
11. Объединяет каналы через `RRF`.
12. Считает `retrieval_score` и `retrieval_reasons`.
13. Применяет baseline ranking и personalization.
14. При необходимости вызывает ML ranking provider.
15. Сохраняет `search_session` и `search_submitted` event.
16. Возвращает ранжированные результаты и explainability metadata.

## Разделение ответственности

### Что принадлежит Backend

- публичный API
- orchestration поиска
- хранение каталога
- candidate generation
- spell correction source of truth
- synonyms source of truth
- fallback ranking
- sessions и events
- explainability response

### Что принадлежит ML service

- reranking внутри candidate set
- learned ranking features
- semantic and intent scoring
- model versioning
- model-based ranking outputs

## Точка интеграции

Актуальная схема:

```text
query
-> normalization and corrections
-> term expansion
-> BM25 / trigram / synonym BM25 / semantic recall
-> RRF
-> candidate set
-> ML reranker
-> final ranking
```

Backend должен:

- подготовить candidates и query context
- вызвать ML service
- смержить ML scores в финальный response

Если ML service недоступен, backend обязан откатиться на baseline ranking.

## Request От Backend К ML

### Обязательные поля

- `query.original`
- `query.normalized`
- `query.corrected`
- `query.applied_synonyms`
- `actor.user_id`
- `actor.organization_id`
- `user_profile`
- `org_profile`
- `candidates`

### Поля кандидата

Каждый candidate желательно передавать минимум с таким набором:

- `id`
- `title`
- `description`
- `category`
- `supplier`
- `attributes`
- `baseline_score`
- `retrieval_score`
- `retrieval_reasons`

### Пример request

```json
{
  "query": {
    "original": "принтэр для офиса",
    "normalized": "принтэр для офиса",
    "corrected": "принтер для офиса",
    "applied_synonyms": ["оргтехника"]
  },
  "actor": {
    "user_id": "user_1",
    "organization_id": "org_1"
  },
  "user_profile": {
    "top_categories": ["Офис", "ИТ"],
    "recent_ste_ids": ["ste_101", "ste_108"],
    "top_suppliers": ["ООО \"Поставка плюс\""],
    "popular_queries": ["принтер", "бумага"]
  },
  "org_profile": {
    "top_categories": ["Офис", "ИТ"],
    "popular_ste_ids": ["ste_101", "ste_108", "ste_111"]
  },
  "candidates": [
    {
      "id": "ste_102",
      "title": "Поставка лазерных принтеров",
      "description": "Принтеры для офиса",
      "category": "Офис",
      "supplier": "ООО \"Поставка плюс\"",
      "attributes": {
        "type": "laser"
      },
      "baseline_score": 0.63,
      "retrieval_score": 0.77,
      "retrieval_reasons": [
        "retrieval_bm25",
        "retrieval_fuzzy",
        "retrieval_rrf"
      ]
    }
  ]
}
```

## Response От ML К Backend

### Обязательные поля

- `items[].id`
- `items[].score`

### Желательные поля

- `items[].reasons`
- `model_version`

### Пример response

```json
{
  "items": [
    {
      "id": "ste_102",
      "score": 0.93,
      "reasons": ["semantic_match", "intent_match", "category_affinity"]
    }
  ],
  "model_version": "reranker_v2"
}
```

## Поведение Backend После Ответа ML

Backend должен:

1. Сопоставить ML scores с candidate set по `id`.
2. Отсортировать candidates по ML score.
3. При необходимости применить финальные business rules после ML.
4. Вернуть существующую frontend schema без зависимости от ML internals.

## Fallback Policy

Если ML service:

- timeout-ится
- недоступен
- возвращает невалидный payload
- возвращает scores только для части кандидатов

backend обязан:

- залогировать ошибку
- не ломать search request
- вернуть baseline ranking

## Операционные ожидания

- candidate set size для ML: `top 50`
- целевая latency ML rerank: `150-300 ms`
- hard timeout backend на вызов ML: `300-500 ms`
- на timeout всегда возвращать fallback ranking

## Что не ожидается от ML

ML service не должен владеть:

- публичным API
- auth
- database persistence
- catalog CRUD
- session storage
- event ingestion
- suggestion history
- spell correction source of truth
- synonyms source of truth

## Текущий Non-ML Baseline

Текущий baseline уже включает:

- dictionary spell corrections
- fuzzy spell corrections по edit distance
- correction неправильной раскладки
- `pymorphy3` lemmatization
- domain expansions и synonyms
- `BM25` retrieval
- `trigram` retrieval
- `synonym-expanded BM25`
- `semantic vector recall` на `BAAI/bge-m3` с fallback на TF-IDF/SVD
- `RRF` fusion
- rule-based ranking
- rule-based personalization
- explainability reasons

Этот baseline должен оставаться рабочим и без ML, и при временных отказах ML service.
