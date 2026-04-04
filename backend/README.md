# Backend

FastAPI backend для каталога, поиска и ML reranking.

## Режим данных

Backend теперь работает без synthetic bootstrap:
- основной режим `BOOTSTRAP_DATASET=portal_csv`
- fallback-режимы для bootstrap убраны
- synthetic dataset из bootstrap исключен полностью

CSV по умолчанию:
- `../ML/data/orig/СТЕ_20260403/СТЕ_20260403.csv`
- `../ML/data/orig/Контракты_20260403/Контракты_20260403.csv`

## Рекомендуемый локальный режим

Для локальной отладки backend сейчас удобно запускать в retrieval-first конфигурации:

```env
RANKING_MODE=retrieval_only
RANKING_PROVIDER=noop
SEARCH_SEMANTIC_BACKEND=disabled
SEARCH_INDEX_CACHE_PATH=/app/.cache/search/hybrid_search_index.pkl
```

Что это даёт:
- выдача строится только по retrieval score, без ML rerank
- semantic warmup не тратит время и память
- индекс сохраняется на диск и не пересчитывается полностью на каждом рестарте

## Импорт каталога и warmup

Для `.env.example` выставлены dev-лимиты:

```env
PORTAL_IMPORT_STE_LIMIT=10000
PORTAL_IMPORT_CONTRACT_LIMIT=10000
PORTAL_IMPORT_PURCHASE_HISTORY_LIMIT=120
```

Если нужен полный каталог, увеличь лимиты или поставь `0`.

Во время bootstrap backend:
- очищает строки CSV от `NUL (0x00)` и другого мусора
- корректно грузит `categories`, `suppliers`, `ste_items`
- пропускает повторный импорт, если каталог уже загружен
- умеет переимпортировать каталог, если текущий объём в БД не соответствует лимиту

Warmup search stack теперь:
- логирует длительность `search_warmup` и `ranking_warmup`
- использует persisted search index cache
- строит retrieval index один раз и загружает его на следующих стартах

Проверка состояния:

```bash
curl -s http://localhost:8000/api/v1/debug/search-stack
```

Ищи поля:
- `search_warmup`
- `search_warmup_duration_seconds`
- `search_documents_count`
- `semantic_backend`

## Производительность и пул соединений

Для снижения `sqlalchemy.exc.TimeoutError: QueuePool limit ...` backend поддерживает настройки пула через env:

```env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=60
DATABASE_POOL_RECYCLE=1800
```

Дополнительно:
- demo-профили и справочники категорий/поставщиков кэшируются в процессе
- retrieval использует two-stage pipeline: cheap candidate generation -> shortlist -> expensive exact/attribute/fuzzy
- typo correction использует индексированный spell vocabulary вместо полного перебора словаря на каждый запрос
- search service хранит `query_variants` с confidence и не форсирует medium-confidence correction как единственный запрос
- protected typo tokens не переисправляются: brand/model/code/size термы вроде `hp`, `12a`, `a4`, `usb`, `ssd` остаются как есть

## Локальный запуск

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e .
alembic upgrade head
python -m app.bootstrap
uvicorn app.main:app --reload
```

## Makefile

Полезные команды:

```bash
cd backend
make build-orig-dataset
make split-orig
make train-ranker
make ml-prepare
make seed-portal
make run
```

## ML и debug

Проверить состояние search stack:

```bash
curl -s http://localhost:8000/api/v1/debug/search-stack
```

Разобрать конкретный запрос без записи telemetry:

```bash
curl -s -X POST "http://localhost:8000/api/v1/debug/search-ranking" \
  -H "Content-Type: application/json" \
  -d '{"query":"сервер для офиса","filters":{"strict_match":false}}'
```

## ML артефакты

Backend читает модель из:

```text
../ML/models/catboost_ranker_v1
```

После обновления артефактов перезапусти backend.
