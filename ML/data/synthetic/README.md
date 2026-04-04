# Синтетический датасет ML

Набор данных для разработки и отладки ML-пайплайна персонализированного поиска без зависимости от продовых данных.

## Назначение

- быстрый запуск end-to-end пайплайна ранжирования;
- воспроизводимые эксперименты (фиксируемый `Seed`);
- проверка фичей персонализации, синонимов и исправления опечаток;
- подготовка train/val/test для модели reranking.

## Генерация данных

Из корня `my-app`:

```powershell
powershell -ExecutionPolicy Bypass -File .\ML\tools\generate_synthetic_data.ps1
```

Пример генерации большего датасета:

```powershell
powershell -ExecutionPolicy Bypass -File .\ML\tools\generate_synthetic_data.ps1 `
  -Organizations 20 `
  -UsersPerOrg 12 `
  -Suppliers 50 `
  -Items 5000 `
  -SessionsPerUser 40 `
  -Seed 123
```

## Загрузка в backend БД

Из корня `my-app`:

```bash
python ML/tools/load_synthetic_to_backend.py
```

С кастомной папкой данных:

```bash
python ML/tools/load_synthetic_to_backend.py --data-dir ML/data/synthetic
```

## Построение ML сплитов

Из корня `my-app`:

```bash
python ML/tools/build_ml_splits.py
```

Скрипт формирует:

- `ML/data/synthetic/splits/train_ranker.csv`
- `ML/data/synthetic/splits/val_ranker.csv`
- `ML/data/synthetic/splits/test_ranker.csv`
- `ML/data/synthetic/splits/split_stats.json`

В `*_ranker.csv` дополнительно сохраняются поля:

- `item_category_name`
- `item_supplier_name`

Это нужно для корректных персонализационных фич `name ↔ name` (без mismatch `id ↔ name`).

## Состав файлов

- `organizations.csv`: организации.
- `users.csv`: пользователи и привязка к организации.
- `categories.csv`: категории каталога.
- `suppliers.csv`: поставщики.
- `ste_items.csv`: карточки СТЕ с атрибутами.
- `synonyms.csv`: словарь синонимов.
- `spell_corrections.csv`: словарь исправления опечаток.
- `purchase_history.csv`: история закупок.
- `search_sessions.csv`: поисковые сессии.
- `search_events.csv`: события в сессиях (`search_submitted`, `result_clicked`, `favorite_added`, `purchase_completed`).
- `user_search_profiles.csv`: агрегированный профиль пользователя.
- `org_search_profiles.csv`: агрегированный профиль организации.
- `query_relevance.csv`: обучающая таблица ранжирования (`query -> candidate -> label`).

## Семантика `label` в `query_relevance.csv`

- `0`: нерелевантный кандидат;
- `1`: слабая релевантность (в т.ч. совпадение по пользовательскому интересу/просмотр);
- `2`: клик по результату;
- `3`: покупка (сильный положительный сигнал).
