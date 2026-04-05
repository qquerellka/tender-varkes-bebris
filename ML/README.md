# ML Workspace

Папка `ML` содержит real-data-only ML pipeline для reranking.

## Что здесь есть

- `tools/build_portal_dataset.py` - собирает ML-ready датасет из raw portal CSV
- `tools/build_ml_splits.py` - строит train/val/test ranking splits из `ML/data/orig/derived`
- `tools/train_ranker.py` - обучает `CatBoostRanker`
- `models/catboost_ranker_v1` - артефакты модели для backend
- `notebooks/` - ноутбуки для экспериментов и демо

## Источник данных

Основной источник:
- `ML/data/orig/СТЕ_20260403/СТЕ_20260403.csv`
- `ML/data/orig/Контракты_20260403/Контракты_20260403.csv`

Производные таблицы и сплиты:
- `ML/data/orig/derived`
- `ML/data/orig/derived/splits`

## Важные ограничения

- synthetic dataset больше не используется
- semantic retrieval features по-прежнему можно держать выключенными, но `emb_*` признаки из precomputed item embeddings теперь поддерживаются в splits, training и local ML provider
- ML reranker работает только как перестановка уже найденных кандидатов

## Что изменилось в pipeline

Текущий pipeline строится вокруг `orig -> derived` и нового retrieval path:
- `tools/build_portal_dataset.py` собирает датасет только из `ML/data/orig`
- retrieval feature enrichment использует новый builder/search path, совместимый с новым каталогом
- candidate pool для ML датасета расширяется через retrieval на новом индексе, без старого synthetic flow
- offline pipeline не рассчитывает semantic retrieval features

Это означает, что обучение и инференс локального ranker теперь завязаны на те же нормализованные сущности, что и runtime backend search.

## Базовый workflow

```bash
python ML/tools/build_portal_dataset.py
python ML/tools/build_ml_splits.py --source-dir ML/data/orig/derived --output-dir ML/data/orig/derived/splits --embeddings-path ML/data/orig/item_embeddings.float32.npy --ste-csv-path ML/data/orig/РЎРўР•_20260403/РЎРўР•_20260403.csv
python ML/tools/train_ranker.py --splits-dir ML/data/orig/derived/splits --artifacts-dir ML/models/catboost_ranker_v1
```

Если нужно собрать датасет на полном каталоге, сначала убедись, что `ML/data/orig/...` содержит актуальные CSV, а затем пересобери `derived` и `splits`.

## Артефакты модели

В `ML/models/catboost_ranker_v1` ожидаются:
- `catboost_ranker.cbm`
- `model_info.json`
- `params.json`
- `metrics.json`
- `feature_importance.csv`

## Интеграция с backend

Backend читает артефакты из:

```text
/app/ML/models/catboost_ranker_v1
```

После переобучения нужен перезапуск backend, чтобы он перечитал артефакты.
