# Tender Portal MVP

MVP-каталог СТЕ для сценариев закупки, поиска и ML reranking.

В репозитории есть:
- `frontend` на `React + Vite`
- `backend` на `FastAPI + PostgreSQL + SQLAlchemy + Alembic`
- `ML` со сборкой датасета из реальных CSV портала и обучением CatBoost reranker

## Главное изменение

Проект теперь работает в `orig-only` режиме:
- synthetic dataset больше не используется
- bootstrap работает только через `portal_csv`, без fallback на demo
- основной источник ML-данных: `ML/data/orig`
- ML-признаки не используют semantic feature columns

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

После запуска:
- frontend: `http://localhost:3000`
- backend: `http://localhost:8000`
- swagger: `http://localhost:8000/docs`

По умолчанию backend ожидает real CSV в:
- `ML/data/orig/СТЕ_20260403/СТЕ_20260403.csv`
- `ML/data/orig/Контракты_20260403/Контракты_20260403.csv`

## Текущий runtime-профиль

По умолчанию проект сейчас настроен под быстрый retrieval-first запуск на portal CSV:
- bootstrap идёт через `portal_csv`, без synthetic fallback
- основной режим ранжирования для локальной отладки: `RANKING_MODE=retrieval_only`
- semantic retrieval можно отключить через `SEARCH_SEMANTIC_BACKEND=disabled`
- search index сохраняется на диск и переиспользуется между рестартами контейнера

В `.env.example` выставлены dev-safe лимиты импорта:
- `PORTAL_IMPORT_STE_LIMIT=10000`
- `PORTAL_IMPORT_CONTRACT_LIMIT=10000`

Это нужно, чтобы первый импорт и warmup были предсказуемыми на локальной машине. Для полного каталога увеличь лимиты или поставь `0`.

## Что изменилось в поиске

- retrieval переписан под новый каталог из `ML/data/orig`
- тяжёлые retrieval-каналы работают по shortlist кандидатов, а не по всему каталогу
- typo/fuzzy correction больше не сканирует весь словарь на каждый запрос, а использует spell vocabulary по полезным catalog-токенам
- query correction теперь формирует набор variants с confidence: high-confidence вариант может стать primary query, а medium-confidence вариант ищется параллельно с original
- typo pipeline защищает brand/model/code/size токены и не пытается переисправлять `hp`, `12a`, `a4`, `usb`, `ssd` и похожие артикулы
- search warmup пишет тайминг и может грузить уже сохранённый индекс вместо полного rebuild
- backend использует более широкий DB connection pool для снижения `QueuePool timeout` под параллельными запросами

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
- `ML/models/catboost_ranker_v1` остается директорией артефактов для backend
- offline ML pipeline использует только `orig`-данные и не добавляет semantic feature columns
