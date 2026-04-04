# Backend

FastAPI backend для каталога, поиска и ML reranking.

## Режим данных

Backend работает без synthetic bootstrap:
- основной режим `BOOTSTRAP_DATASET=portal_csv`
- CSV по умолчанию читаются из `../ML/data/orig/...`
- synthetic dataset исключён из текущего runtime-пути

## Рекомендуемый локальный режим

Для локальной отладки backend сейчас рассчитан на retrieval-first конфигурацию:

```env
RANKING_MODE=retrieval_only
RANKING_PROVIDER=noop
SEARCH_RETRIEVAL_BACKEND=postgres
SEARCH_SEMANTIC_BACKEND=disabled
SEARCH_SEMANTIC_USE_FAISS=false
```

Что это даёт:
- выдача строится только по retrieval score, без ML rerank
- startup не пытается строить глобальный in-memory индекс по всему каталогу
- семантика полностью выключена и не расходует память на embeddings, FAISS или TF-IDF/SVD артефакты
- typo/fuzzy correction остаются доступны без возврата к тяжёлому runtime-индексу

## Как сейчас работает поиск

1. Search service нормализует запрос и строит query variants:
   - original query
   - spell correction из таблицы `spell_corrections`
   - keyboard layout correction
   - fuzzy correction через lightweight spell vocabulary
2. Lightweight spell vocabulary собирается из:
   - `spell_corrections`
   - `synonyms`
   - токенов из `title`, `category`, `attributes_json`
   Это позволяет вернуть typo/fuzzy поведение без полного `HybridSearchIndex`.
3. Candidate generation по умолчанию идёт в PostgreSQL:
   - FTS-канал для основного lexical query
   - FTS-канал для morphology terms
   - FTS-канал для synonym terms
   - RRF-слияние SQL ranking lists
4. `pg_trgm` используется только как fallback:
   - включается, если FTS дал слишком мало уникальных кандидатов
   - работает по `title`, а не по широкому `attributes_json`, чтобы не раздувать latency
5. Дальше ветвление зависит от режима:
   - `retrieval_only` и не-`strict_match`: repository возвращает `SearchCandidateRef` сразу из SQL RRF
   - `strict_match` или не-`retrieval_only`: PostgreSQL даёт shortlist, после чего маленький `HybridSearchIndex` строится только на shortlist и запускает exact/attribute/fuzzy phase
6. Payload подгружается поздно:
   - retrieval хранит компактные refs/features
   - для top-N грузится `SearchItemSnapshot`
   - snapshot использует `attributes_text` и `attribute_value_count` вместо полного `attributes` dict

## Search backend'ы

### `postgres` backend

Это текущий default:

```env
SEARCH_RETRIEVAL_BACKEND=postgres
```

Особенности:
- быстрый startup
- нет полного прогрева memory-индекса на `/ready`
- основная нагрузка перенесена в PostgreSQL FTS и `pg_trgm`
- лучший профиль по RAM для больших каталогов

### `memory` backend

Опциональный режим:

```env
SEARCH_RETRIEVAL_BACKEND=memory
```

Особенности:
- строит глобальный `HybridSearchIndex`
- может использовать persisted cache из `SEARCH_INDEX_CACHE_PATH`
- тяжелее по startup time и RAM
- нужен только если ты сознательно возвращаешься к старому full in-memory retrieval

## Warmup и readiness

Startup search warmup теперь зависит от backend:

- для `postgres` backend вызывается лёгкий `warmup_search_backend()`
- он не строит глобальный индекс, а только проверяет backend и считает документы
- `semantic_backend` в runtime-report всегда `disabled`

`/ready` станет `200` только когда:
- `search_warmup == ready`
- `ranking_warmup == ready`

Проверка состояния:

```bash
curl -s http://localhost:8000/api/v1/debug/search-stack
```

Полезные поля:
- `search_warmup`
- `search_warmup_duration_seconds`
- `search_documents_count`
- `semantic_backend`
- `ranking_provider_name`

## Импорт каталога и лимиты

В `.env.example` выставлены dev-лимиты:

```env
PORTAL_IMPORT_STE_LIMIT=10000
PORTAL_IMPORT_CONTRACT_LIMIT=10000
PORTAL_IMPORT_PURCHASE_HISTORY_LIMIT=120
```

Если нужен полный каталог, увеличь лимиты или поставь `0`.

Во время bootstrap backend:
- очищает CSV от мусорных символов
- загружает `categories`, `suppliers`, `ste_items`
- пропускает повторный импорт, если каталог уже загружен

## Производительность

Сейчас основные рычаги скорости такие:
- держать `SEARCH_RETRIEVAL_BACKEND=postgres`
- для локального режима оставлять `RANKING_MODE=retrieval_only`
- не включать semantic retrieval
- следить, чтобы были применены миграции с `pg_trgm` и hybrid search indexes

Для текущего алгоритма важно понимать:
- FTS является основным путём
- trigram search является fallback, а не always-on каналом
- `retrieval_only` больше не строит mini-`HybridSearchIndex` на каждый запрос
- строгие и rerank-сценарии всё ещё могут строить маленький shortlist-индекс, но не индекс всего корпуса

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

## Debug

Разобрать search stack:

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
