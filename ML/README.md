# ML Workspace

Папка `ML` содержит ML-часть проекта персонализированного поиска:

- synthetic dataset и ranking splits
- скрипты подготовки данных и обучения
- ноутбуки для экспериментов и демо
- сохранённые артефакты ранжирования для backend

Текущая схема поиска в проекте двухэтапная:

1. backend делает понимание запроса, извлечение и генерацию кандидатов
2. ML переставляет уже найденный набор кандидатов

## Назначение

ML-слой в проекте отвечает за:

- обучение reranker-моделей
- расчёт ranking-метрик
- подготовку артефактов для backend
- офлайн-эксперименты и demo notebook

ML-слой не отвечает за:

- хранение каталога
- публичный API
- source of truth для spell correction
- source of truth для synonyms
- search sessions и events
- retrieval с нуля

## Структура

- `tools/`: генерация synthetic data, построение сплитов, обучение моделей
- `data/synthetic/`: synthetic dataset и ranking splits
- `models/`: сохранённые артефакты моделей
- `notebooks/`: ноутбуки для экспериментов и презентации

## Текущий Алгоритм

### Stage 1. Query Understanding В Backend

Backend отвечает за извлечение кандидатов и стабильный резервный режим.

На каждом запросе backend:

1. нормализует query
2. применяет dictionary spell correction
3. применяет fuzzy spell correction по vocabulary каталога
4. исправляет неверную раскладку клавиатуры
5. делает морфологическое и доменное расширение терминов
6. выделяет structured query signals:
   - бренды
   - модели и коды
   - числа, фасовки и quantity constraints
   - единицы измерения и size tokens
   - category hints и attribute hints
7. подмешивает synonyms из backend storage с `source` и `weight`

### Stage 2. Гибридное Извлечение

После этого backend запускает несколько retrieval-каналов:

- `exact / structured retrieval`
- `attribute retrieval`
- `fielded BM25`
- `morphology-aware BM25`
- `trigram shortlist -> Damerau-Levenshtein fuzzy retrieval`
- `synonym-expanded BM25`
- `семантическое извлечение по эмбеддингам` на `BAAI/bge-m3`
  - плотные эмбеддинги строятся для запроса и товара
  - векторный индекс использует `FAISS`, если зависимость доступна
  - если модель плотных эмбеддингов или `FAISS` недоступны, backend откатывается на резервный слой TF-IDF + символьные n-граммы + SVD

Каналы объединяются через `weighted RRF` (взвешенный Reciprocal Rank Fusion).

На выходе каждый кандидат уже содержит:

- `retrieval_score`
- `retrieval_reasons`
- `retrieval_channel_scores`
- `retrieval_channel_ranks`
- `retrieval_features`
- текстовые поля и attributes
- user/org personalization context

### Stage 3. Baseline Ranking

Перед ML backend считает rule-based baseline score.

В нём используются:

- exact, prefix и partial match по title
- match по description
- token overlap
- `attribute_match`
- `brand_match`
- `numeric_constraint_match`
- `category_match`
- retrieval score
- purchase history match
- recent interaction
- supplier popularity
- organization popularity

Это базовое ранжирование остаётся рабочим резервным режимом, если ML недоступен.

### Stage 4. ML Reranking

ML не ищет товары с нуля.
Он только переставляет уже найденный набор кандидатов.

Текущая основная модель:

- `CatBoostRanker` с `YetiRankPairwise`

Backend `LocalMlRankingProvider` сейчас поддерживает два режима артефактов:

- `CatBoost` артефакты из `ML/models/catboost_ranker_v1`
- legacy `ridge + tfidf` артефакты для обратной совместимости

При обработке запросов backend строит признаки ранжирования и смешивает:

- `0.7 * ML prediction`
- `0.2 * baseline score`
- `0.1 * retrieval score`

Это безопаснее, чем полностью заменять baseline ranking одним только ML score.

## Быстрые Команды

Из корня `my-app`:

Для локального ML-цикла на Windows удобнее использовать Python `3.12`.
Если хочешь собирать сплиты с тем же dense semantic backend, что и в Docker, сначала установи backend-зависимости для семантического поиска:

```bash
python -m pip install -e "./backend[semantic]"
```

Сгенерировать synthetic dataset:

```powershell
powershell -ExecutionPolicy Bypass -File .\ML\tools\generate_synthetic_data.ps1
```

Загрузить synthetic data в backend:

```bash
python ML/tools/load_synthetic_to_backend.py
```

Пересобрать ranking splits:

```bash
python ML/tools/build_ml_splits.py
```

Обучить CatBoost ranker и сохранить артефакты:

```bash
python ML/tools/train_ranker.py --artifacts-dir ML/models/catboost_ranker_v1
```

Открыть demo notebook:

```text
ML/notebooks/tender-search-catboost-ranker-demo.ipynb
```

## Ranking Splits

`ML/tools/build_ml_splits.py` строит time-based train/val/test splits из synthetic relevance log.
Во время сборки он дополнительно запускает offline enrichment через `ML/tools/retrieval_feature_enrichment.py`, чтобы в сплиты попали retrieval-сигналы из текущего hybrid search pipeline.

При построении строка сплита обогащается полями:

- `item_title`
- `item_description`
- category и supplier metadata
- user search profile
- organization search profile
- `retrieval_score`
- `retrieval_channel_count`
- hit-флаги каналов recall:
  - `retrieval_exact`
  - `retrieval_attribute`
  - `retrieval_bm25`
  - `retrieval_morphology`
  - `retrieval_fuzzy`
  - `retrieval_synonym`
  - `retrieval_semantic`
  - `retrieval_rrf`
- per-channel scores и per-channel ranks
- structured retrieval flags:
  - `exact_match_flag`
  - `phrase_match_flag`
  - `category_match_flag`
  - `brand_match_flag`
  - `numeric_constraint_match_flag`
  - `attribute_overlap_count`
  - `appeared_in_multiple_channels`
- query-level признаки:
  - `query_has_correction`
  - `query_has_synonyms`
- признаки semantic backend:
  - `semantic_backend_bge_m3`
  - `semantic_backend_fallback`
  - `semantic_via_faiss`

Результат сохраняется в:

- `ML/data/synthetic/splits/train_ranker.csv`
- `ML/data/synthetic/splits/val_ranker.csv`
- `ML/data/synthetic/splits/test_ranker.csv`
- `ML/data/synthetic/splits/split_stats.json`

В `split_stats.json` дополнительно сохраняется блок `retrieval_enrichment`.
По нему удобно проверять, на каком semantic backend реально были собраны сплиты:

- `semantic_backend = bge_m3` значит enrichment шёл через `BAAI/bge-m3`
- `semantic_backend = tfidf_svd` значит offline enrichment откатился на резервный слой

## Pipeline Обучения

`ML/tools/train_ranker.py` это текущая воспроизводимая точка входа для обучения reranker.

Скрипт:

1. загружает `train / val / test` splits
2. строит tabular ranking features по query, item metadata, attributes, retrieval signals и user/org profile
3. считает простой baseline по текущей позиции кандидата
4. обучает `CatBoostRanker`
5. считает ranking-метрики на validation и test
6. сохраняет модель, параметры, метрики и feature importance

## Признаки CatBoost

Текущий набор признаков включает:

- длину query и normalized query
- позицию кандидата
- флаги correction и synonym expansion
- совпадение категории с user profile
- совпадение категории с org profile
- совпадение supplier с user profile
- признак recent item
- признак popularity внутри организации
- признак query-in-history
- `baseline_score`
- `retrieval_score`
- `retrieval_channel_count`
- `query_has_synonyms`
- overlap между query и title / description / attributes
- exact / prefix / partial match по title
- contains query по description
- structured retrieval flags:
  - `exact_match_flag`
  - `phrase_match_flag`
  - `category_match_flag`
  - `brand_match_flag`
  - `numeric_constraint_match_flag`
  - `attribute_overlap_count`
  - `appeared_in_multiple_channels`
- channel-level retrieval features:
  - hit-флаги по каналам recall
  - per-channel scores
  - per-channel ranks
- backend-флаги семантического слоя:
  - `semantic_backend_bge_m3`
  - `semantic_backend_fallback`
  - `semantic_via_faiss`
- количество attributes
- длину title и description
- категориальные признаки товара:
  - `item_category_id`
  - `item_category_name`
  - `item_supplier_id`
  - `item_supplier_name`
  - `item_status`

## Метрики

`train_ranker.py` сейчас считает:

- `NDCG@5`
- `NDCG@10`
- `HitRate@5`
- `HitRate@10`
- `MRR@5`
- `MRR@10`
- `MAP@5`
- `MAP@10`

Важно:

- `baseline_*_metrics` в training script это baseline по текущей позиции кандидата
- это не то же самое, что полный backend baseline с business rules и personalization

Поэтому офлайн-результаты пока нужно трактовать как:

- сравнение с простым ranking baseline
- а не как полное сравнение один-в-один с боевым backend search pipeline

И отдельно важно:

- рост `NDCG` не гарантирует рост `HitRate` или `MRR`
- если метрики расходятся, после обучения нужно обязательно руками проверить реальные запросы в UI и через API

## Артефакты Модели

По умолчанию CatBoost-артефакты сохраняются в:

```text
ML/models/catboost_ranker_v1
```

Ожидаемые файлы:

- `catboost_ranker.cbm`
- `model_info.json`
- `params.json`
- `metrics.json`
- `feature_importance.csv`

В проекте также могут оставаться legacy baseline артефакты:

```text
ML/models/baseline_v1
```

Backend всё ещё умеет использовать их как резервный режим совместимости.

## Интеграция С Backend

Провайдер `local_ml` в backend сейчас работает так:

1. если найден `catboost_ranker.cbm`, загружается CatBoost-модель
2. иначе, если найдены `ridge_ranker.joblib` и `tfidf_vectorizer.joblib`, загружается legacy linear reranker
3. иначе backend откатывается на baseline ranking

Путь к ML-артефактам по умолчанию:

```text
/app/ML/models/catboost_ranker_v1
```

Этот путь уже зашит в:

- backend config
- Docker Compose
- local ML provider

После переобучения backend не подхватывает новую модель "на лету".
Нужно перезапустить backend, чтобы `LocalMlRankingProvider` заново загрузил `catboost_ranker.cbm` и новый `model_info.json`.

Если Docker-стек уже запущен, обычно достаточно:

```bash
docker compose restart backend
```

Проверить загрузку можно по логам:

```bash
docker compose logs -f backend
```

Полезные строки:

- `CatBoost ML provider loaded artifacts from /app/ML/models/catboost_ranker_v1`
- `Ranking provider warmup complete: provider=LocalMlRankingProvider`

## Работа Семантического Извлечения

Semantic recall в backend сейчас устроен так:

- основной backend семантического поиска использует `BAAI/bge-m3`
- backend сначала пытается поднять слой плотных эмбеддингов и FAISS-индекс
- если модель плотных эмбеддингов, `FlagEmbedding` или `FAISS` недоступны, извлечение автоматически откатывается на резервный слой TF-IDF + символьные n-граммы + SVD

Для Docker-стека это уже учтено:

- backend-образ ставит semantic-зависимости только если при сборке передать `BACKEND_INSTALL_SEMANTIC=true`
- `docker-compose.yml` монтирует отдельный volume `huggingface_cache` для кэша Hugging Face
- повторный запуск backend использует этот volume и не должен заново скачивать `BAAI/bge-m3`, если не делать `docker compose down -v`

Важно:

- если запускать `docker compose up` без предварительного кэширования модели, backend может долго оставаться в состоянии `ready=503`, пока скачивает и инициализирует `BAAI/bge-m3`
- поэтому для первого запуска лучше отдельно прогреть модель через `docker compose run --rm --no-deps backend ...`, а уже потом поднимать основной стек
- если в окружении нет доступа к сети или модель не может загрузиться, backend продолжит работать на резервном семантическом слое без падения всего поиска

### Проверенный Docker Flow для `BAAI/bge-m3`

Ниже сценарий, который мы проверили для `bash`/WSL. Он отделяет скачивание модели от обычного запуска Docker-стека.

1. Собрать backend с semantic-зависимостями:

```bash
cd /mnt/c/Users/golov/OneDrive/Документы/tender/frontend-template/my-app

docker compose down
BACKEND_INSTALL_SEMANTIC=true docker compose build --no-cache backend
```

2. Один раз скачать и закэшировать `BAAI/bge-m3` в `huggingface_cache`:

```bash
docker compose run --rm --no-deps backend python -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=False); print('BGE-M3 cached')"
```

3. Отдельно поднять `postgres + backend`, дождаться прогрева и только потом запускать frontend:

```bash
docker compose up -d postgres backend
docker compose logs -f backend
```

В логах должны появиться признаки успешного старта:

- нет строки `No module named 'FlagEmbedding'`
- нет повторного `Fetching 30 files` во время обычного `docker compose up`
- есть строка вида `Search warmup complete: semantic_backend=bge_m3`
- `/ready` начинает возвращать `200`

4. После этого можно запускать frontend:

```bash
docker compose up -d frontend
```

Важно:

- `docker compose down -v` удаляет `huggingface_cache`, после этого модель придётся скачивать заново
- если нужен только fallback semantic backend без `bge-m3`, можно не передавать `BACKEND_INSTALL_SEMANTIC=true` и не делать prefetch модели

## Demo Notebook

Основной notebook для презентации:

```text
ML/notebooks/tender-search-catboost-ranker-demo.ipynb
```

Он показывает:

- загрузку splits
- построение features
- position baseline
- обучение CatBoost
- сравнение метрик
- feature importance

Notebook нужен для:

- hackathon demo
- объяснения reranking stage
- быстрых ручных sanity checks

## Workflow Перед Docker

Из корня `my-app`:

1. пересобрать ranking splits

```bash
python ML/tools/build_ml_splits.py
```

2. обучить CatBoost-артефакты

```bash
python ML/tools/train_ranker.py --artifacts-dir ML/models/catboost_ranker_v1
```

3. проверить, что артефакты действительно появились

```text
ML/models/catboost_ranker_v1/catboost_ranker.cbm
ML/models/catboost_ranker_v1/model_info.json
ML/models/catboost_ranker_v1/metrics.json
ML/models/catboost_ranker_v1/feature_importance.csv
```

4. только после этого запускать backend-образ с нужными зависимостями

Для `bash`/WSL:

```bash
BACKEND_INSTALL_SEMANTIC=true docker compose build --no-cache backend
```

Для PowerShell:

```powershell
$env:BACKEND_INSTALL_SEMANTIC='true'
docker compose build --no-cache backend
Remove-Item Env:BACKEND_INSTALL_SEMANTIC
```

5. отдельно прогреть и закэшировать `BAAI/bge-m3`

```bash
docker compose run --rm --no-deps backend python -c "from FlagEmbedding import BGEM3FlagModel; BGEM3FlagModel('BAAI/bge-m3', use_fp16=False); print('BGE-M3 cached')"
```

6. только после этого поднимать `postgres + backend`

```bash
docker compose up -d postgres backend
docker compose logs -f backend
```

7. после появления `semantic_backend=bge_m3` запускать frontend

```bash
docker compose up -d frontend
```

Если стек уже поднят и ты просто переобучил модель на хосте, полной пересборки не нужно.
Обычно достаточно:

```bash
docker compose restart backend
```

Важно:

- папка `ML` монтируется в backend container как `read-only`
- значит артефакты модели должны быть собраны на хосте до запуска Docker
- кэш Hugging Face для `BAAI/bge-m3` хранится отдельно в Docker volume `huggingface_cache`
- если сделать `docker compose down -v`, этот кэш удалится вместе с volume
