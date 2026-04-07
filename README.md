# Tender Portal MVP

Каталог СТЕ для сценариев закупки, поиска и ML reranking.

В репозитории есть:
- `frontend` на `React + Vite`
- `backend` на `FastAPI + PostgreSQL + SQLAlchemy + Alembic`
- `ML` со сборкой датасета из реальных CSV портала и обучением CatBoost reranker

## Что важно сейчас

Проект работает в `orig-only` режиме:
- synthetic dataset больше не используется для bootstrap и runtime
- bootstrap идёт только через `portal_csv`
- основной runtime-путь поиска теперь `DB-first`, а не полный in-memory индекс
- semantic retrieval полностью отключён

Текущий локальный профиль по умолчанию:

```env
RANKING_MODE=retrieval_only
RANKING_PROVIDER=noop
SEARCH_RETRIEVAL_BACKEND=postgres
SEARCH_SEMANTIC_BACKEND=disabled
SEARCH_SEMANTIC_USE_FAISS=false
```

## Структура

- [frontend/README.md](./frontend/README.md)
- [backend/README.md](./backend/README.md)
- [backend/ARCHITECTURE.md](./backend/ARCHITECTURE.md)
- [ML/README.md](./ML/README.md)

## Быстрый старт через Docker

```bash
cp .env.example .env
docker compose up --build
```

Если backend-код менялся, запускай именно с `--build`: контейнер backend собирается в image и не монтирует `./backend` как live volume.

После запуска:
- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- swagger: `http://localhost:8000/docs`

По умолчанию backend ожидает реальные CSV в:
- `ML/data/orig/СТЕ_20260403/СТЕ_20260403.csv`
- `ML/data/orig/Контракты_20260403/Контракты_20260403.csv`

## Как сейчас работает поиск

1. Bootstrap загружает каталог из portal CSV в PostgreSQL.
2. Startup warmup больше не строит полный глобальный `HybridSearchIndex`, если включён `SEARCH_RETRIEVAL_BACKEND=postgres`.
3. Запрос нормализуется, после чего search service строит варианты:
   - оригинальный запрос
   - corrections из `spell_corrections`
   - keyboard layout correction
   - fuzzy correction и fuzzy term expansion через лёгкий spell vocabulary, собранный из БД
4. Candidate generation идёт в PostgreSQL:
   - основной канал: full-text search по `title + description + attributes_json`
   - дополнительные lexical-каналы: morphology и synonym terms
   - результаты SQL-каналов сливаются через RRF
   - `pg_trgm` запускается только как fallback, если FTS дал слишком мало уникальных кандидатов
   - trigram fallback сейчас работает по `title`, чтобы не разгонять latency и RAM на широком `attributes_json` проходе
5. Дальше есть два режима:
   - `retrieval_only` и не-`strict_match`: результаты возвращаются сразу из SQL RRF-слияния, без per-query mini-индекса
   - `strict_match` или не-`retrieval_only`: PostgreSQL сначала даёт shortlist, а затем маленький in-memory `HybridSearchIndex` строится только на shortlist, а не на всём корпусе
6. Runtime-кандидаты больше не тащат полный payload:
   - retrieval оперирует `id` и compact features
   - payload подгружается поздно, только для итоговых top-N
   - snapshot хранит `attributes_text` и `attribute_value_count`, а не полный `attributes` dict

## Текущий runtime-профиль

В `.env.example` выставлены dev-safe лимиты импорта:

```env
PORTAL_IMPORT_STE_LIMIT=10000
PORTAL_IMPORT_CONTRACT_LIMIT=10000
PORTAL_IMPORT_PURCHASE_HISTORY_LIMIT=120
```

Это нужно, чтобы первый импорт и локальный старт были предсказуемыми по времени и памяти. Для полного каталога увеличь лимиты или поставь `0`.

Семантика выключена полностью:

```env
SEARCH_SEMANTIC_BACKEND=disabled
SEARCH_SEMANTIC_USE_FAISS=false
```

`SEARCH_INDEX_CACHE_PATH` остаётся в конфиге только для опционального `memory` backend. В дефолтном `postgres`-режиме startup не зависит от persisted hybrid index.

## Когда нужен memory backend

Старый `HybridSearchIndex` всё ещё доступен как опциональный режим:

```env
SEARCH_RETRIEVAL_BACKEND=memory
```

Но это уже не default-путь. Он потребляет заметно больше RAM, дольше стартует и нужен только если ты сознательно хочешь вернуть полный in-memory retrieval поверх всего корпуса.

## ML workflow

Из корня проекта:

```bash
python ML/tools/build_portal_dataset.py
python ML/tools/build_ml_splits.py --source-dir ML/data/orig/derived --output-dir ML/data/orig/derived/splits
python ML/tools/train_ranker.py --splits-dir ML/data/orig/derived/splits --artifacts-dir ML/models/catboost_ranker_v1
```

После переобучения перезапусти backend:

```bash
docker compose restart backend
```

## Что важно знать

- `BOOTSTRAP_DATASET` по умолчанию теперь `portal_csv`
- offline ML pipeline использует только `orig`-данные и не добавляет semantic feature columns
- быстрый локальный режим сейчас ориентирован на `postgres + retrieval_only`
- если нужна диагностика search stack, смотри `GET /api/v1/debug/search-stack`
