# Backend

FastAPI backend для каталога, поиска и baseline/ML-ранжирования.

## Назначение

- API для каталога и поиска
- гибридное извлечение без обязательного внешнего search engine
- базовое ранжирование и fallback без ML
- rule-based personalization
- хранение search sessions и событий
- точка интеграции для будущего ML reranker
- PostgreSQL + SQLAlchemy + Alembic

## Документы

- `ARCHITECTURE.md` - структура backend
- `ENTITY_REFERENCE.md` - сущности backend, их поля и значения
- `ML_HANDOFF.md` - контракт backend <-> ML
- `TELEMETRY_SPEC.md` - event-модель и search signals
- `TELEMETRY_EVENT_DICTIONARY.md` - словарь raw events и payload
- `TELEMETRY_QA_CHECKLIST.md` - ручная проверка telemetry через debug API

## Локальный запуск

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Для семантического поиска на плотных эмбеддингах:

```bash
pip install -e ".[semantic]"
```

## База данных

Из корня проекта:

```bash
cp .env.example .env
docker compose up -d postgres
```

Затем из `backend`:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python -m app.bootstrap
```

## Запуск API

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

API будет доступен на `http://localhost:8000`, документация на `http://localhost:8000/docs`.

## Что делает bootstrap

Поведение зависит от `BOOTSTRAP_DATASET`:

- `portal_csv` - импортирует реальные CSV портала
- `synthetic` - загружает synthetic dataset из `ML/data/synthetic`
- `demo` - загружает demo data
- `auto` - пытается `portal_csv`, потом `synthetic`, потом `demo`

В `backend/.env.example` по умолчанию стоит `BOOTSTRAP_DATASET=auto`, поэтому локальный запуск обычно не требует обязательного наличия больших CSV.

## Команды Makefile

```bash
cd backend
make install
make db-up
make migrate
make seed
make seed-portal
make run
```

Полезные сценарии:

```bash
cd backend
make bootstrap
make dev
```

`make dev` поднимает PostgreSQL через корневой `docker compose`, выполняет bootstrap и запускает `uvicorn`.

## Полный стек через Docker

Из корня проекта:

```bash
cp .env.example .env
docker compose up --build
```

В Docker backend запускается с параметрами из корневого `.env`:
- `RANKING_MODE=ml_local_baseline`
- `RANKING_PROVIDER=local_ml`
- `BOOTSTRAP_DATASET=auto`

## ML артефакты

В Docker backend по умолчанию ищет артефакты в:

```text
/app/ML/models/catboost_ranker_v1
```

При локальном запуске путь берется из `backend/.env` или из дефолта в коде.

Для подготовки CatBoost артефактов вручную:

```bash
python ML/tools/build_ml_splits.py
python ML/tools/train_ranker.py --artifacts-dir ML/models/catboost_ranker_v1
```

## Быстрый Старт Для ML

Минимальный локальный цикл для ML-инженера:

```bash
cd backend
source .venv/bin/activate
pip install -e ".[semantic]"
cp .env.example .env
alembic upgrade head
python -m app.bootstrap
uvicorn app.main:app --reload
```

Полезно проверить сразу после старта:

```bash
curl -s http://localhost:8000/api/v1/debug/search-stack | jq
```

Для dry-run разбора одного запроса без записи `search_session` и telemetry:

```bash
curl -s -X POST "http://localhost:8000/api/v1/debug/search-ranking" \
  -H "Content-Type: application/json" \
  -H "X-Demo-User-Id: demo_customer_it" \
  -d '{
    "query": "сервер для офиса",
    "filters": {
      "strict_match": false
    }
  }' | jq
```

Этот endpoint отдает:
- query normalization context
- expanded terms и structured query hints
- profile snapshot
- candidate set с `baseline_score`, `retrieval_score`, `retrieval_features`
- final ranking с `final_rank`, `final_score`, `score_delta`
- статус ranking provider и fallback

Для выгрузки live dataset в формат, совместимый с `ML/tools/build_ml_splits.py`:

```bash
cd backend
source .venv/bin/activate
python -m app.export_ml_dataset \
  --output-dir ../ML/data/live_export \
  --build-splits
```

Полезные опции:
- `--user-id demo_customer_it`
- `--organization-id org_it`
- `--limit-sessions 200`

Команда экспортирует:
- `search_sessions.csv`
- `search_events.csv` и `search_events.jsonl`
- `search_impressions.csv`
- `query_relevance.csv`
- `user_item_features.csv`
- справочники каталога и profile tables
- `export_metadata.json`

## Импорт реальных CSV портала

Поддержан импорт файлов:
- `../СТЕ_20260403.csv`
- `../Контракты_20260403.csv`

Запуск:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
python -m app.import_portal_csv \
  --ste-csv ../СТЕ_20260403.csv \
  --contracts-csv ../Контракты_20260403.csv
```

Или:

```bash
cd backend
make migrate
make seed-portal
```

Если нужен bootstrap через `python -m app.bootstrap`, выставьте:

```bash
BOOTSTRAP_DATASET=portal_csv
```

Дополнительные переменные:

- `PORTAL_STE_CSV_PATH`
- `PORTAL_CONTRACTS_CSV_PATH`
- `PORTAL_IMPORT_STE_LIMIT`
- `PORTAL_IMPORT_CONTRACT_LIMIT`
- `PORTAL_IMPORT_PURCHASE_HISTORY_LIMIT`

## Полезные ручки

```text
GET  /health
GET  /docs
GET  /redoc
GET  /api/v1/catalog/categories
GET  /api/v1/catalog/suppliers
GET  /api/v1/catalog/ste/{ste_id}
GET  /api/v1/catalog/ste/{ste_id}/related
GET  /api/v1/profile/search
GET  /api/v1/search/suggestions?query=ав
GET  /api/v1/search/spellcheck?query=абтобус
GET  /api/v1/search/history
POST /api/v1/search
POST /api/v1/events
POST /api/v1/debug/search-ranking
GET  /api/v1/debug/search-stack
GET  /api/v1/debug/telemetry/events
GET  /api/v1/debug/telemetry/impressions
GET  /api/v1/debug/telemetry/health
```
