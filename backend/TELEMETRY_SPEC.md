# Спецификация Telemetry И Search Signals

Этот документ фиксирует event-модель проекта для frontend, backend и ML.

Цель:
- одинаково понимать названия событий
- не смешивать `raw events`, `business state` и `derived features`
- дать ML-инженерам стабильный источник истины по логам

Для краткой event-by-event расшифровки смотри также [TELEMETRY_EVENT_DICTIONARY.md](./TELEMETRY_EVENT_DICTIONARY.md).
Для ручной проверки telemetry через debug API смотри [TELEMETRY_QA_CHECKLIST.md](./TELEMETRY_QA_CHECKLIST.md).

## Слои Данных

### 1. Raw events

Это сырые действия пользователя.

Основные таблицы:
- `search_events`
- `search_impressions`
- `search_sessions`

### 2. Business state

Это текущее пользовательское состояние и предметные сущности.

Основные таблицы:
- `favorites`
- `comparison_items`
- `cart_items`
- `purchase_history`

### 3. Derived features

Это агрегаты, которые считаются поверх raw events и business state.

Примеры:
- `user_item_click_count`
- `user_supplier_affinity_score`
- `user_category_affinity_score`
- `global_item_ctr`
- `impressions_without_clicks`
- `avg_dwell_ms`

Derived features не должны быть единственным источником истины. Истина всегда в raw events и business tables.

## Текущие Таблицы

### search_sessions

Одна запись на один поисковый запрос.

Ключевые поля:
- `id`
- `user_id`
- `organization_id`
- `query`
- `normalized_query`
- `created_at`

### search_events

Append-only журнал действий вокруг поиска и карточек.

Ключевые поля:
- `id`
- `session_id`
- `user_id`
- `organization_id`
- `role`
- `event_type`
- `ste_id`
- `supplier_id`
- `category_id`
- `query_text`
- `normalized_query`
- `corrected_query`
- `page_type`
- `page_url`
- `referrer`
- `rank_position`
- `results_page`
- `payload_json`
- `created_at`

### search_impressions

Показы элементов в выдаче.

Ключевые поля:
- `id`
- `search_session_id`
- `user_id`
- `organization_id`
- `ste_id`
- `supplier_id`
- `category_id`
- `rank_position`
- `results_page`
- `visible`
- `rendered_at`

## Канонический Список Event Types

### Search session

- `search_submitted`
  Что значит:
  Пользователь отправил поисковый запрос.

- `search_results_rendered`
  Что значит:
  Backend вернул выдачу, а frontend её отрисовал.

- `search_refined`
  Что значит:
  Пользователь после одной выдачи сформулировал новый запрос.

- `search_abandoned`
  Что значит:
  Пользователь ушёл на новый запрос без полезного взаимодействия с предыдущей выдачей.

### Impressions

- `search_impression`
  Что значит:
  Конкретная карточка была показана пользователю в выдаче.

Примечание:
  В проекте сами показы пишутся в `search_impressions`, а не только в `search_events`.

### Result interaction

- `result_clicked`
  Что значит:
  Пользователь открыл карточку из выдачи обычным кликом.

- `result_opened`
  Что значит:
  Карточка товара реально открылась.

- `result_opened_new_tab`
  Что значит:
  Карточка была открыта в новой вкладке через middle click / аналогичный сценарий.

### Product detail

- `product_view_started`
  Что значит:
  Пользователь начал просмотр карточки товара.

- `product_view_ended`
  Что значит:
  Пользователь покинул карточку товара.

  Ожидаемый payload:
  - `dwell_ms`

- `quick_back`
  Что значит:
  Пользователь быстро покинул карточку.

  Это негативный сигнал. Сейчас фиксируется как отдельный raw event.

- `item_copy`
  Что значит:
  Пользователь скопировал текст с карточки.

  Ожидаемый payload:
  - `selection_length`
  - `copied_text` — только сокращённый фрагмент, без длинных данных

### Collections and intent

- `favorite_added`
- `favorite_removed`
- `comparison_added`
- `comparison_removed`
- `compare_viewed`
- `cart_added`
- `cart_removed`
- `cart_quantity_changed`

### Filters and controls

- `filter_applied`
- `filter_removed`
- `filters_cleared`
- `sort_changed`

Ожидаемый payload:
- `filter_name`
- `filter_value`

### Conversion

- `purchase_completed`

Ожидаемый payload:
- `quantity`
- `price`
- `contract_id`

### Quality and diagnostics

- `scroll_depth_changed`
  Что значит:
  Пользователь доскроллил выдачу до порога.

  Ожидаемый payload:
  - `depth_percent`
  - `visible_results`

- `irrelevant_marked`
  Что значит:
  Пользователь явно пометил результат как нерелевантный.

## Какие События Уже Реально Логируются

На текущем этапе проект уже пишет:
- `search_submitted`
- `search_results_rendered`
- `search_impression`
- `suggestion_clicked`
- `result_clicked`
- `result_opened`
- `result_opened_new_tab`
- `product_view_started`
- `product_view_ended`
- `quick_back`
- `item_copy`
- `irrelevant_marked`
- `favorite_added`
- `favorite_removed`
- `comparison_added`
- `comparison_removed`
- `compare_viewed`
- `cart_added`
- `cart_removed`
- `cart_quantity_changed`
- `filter_applied`
- `filter_removed`
- `filters_cleared`
- `sort_changed`
- `scroll_depth_changed`
- `search_refined`
- `search_abandoned`
- `purchase_intent`
- `purchase_completed`

## Что Является Derived Feature, А Не Raw Event

Нельзя считать это первичными событиями:
- `dwell_time`
- `pogo_sticking`
- `impressions_without_clicks`
- `user_supplier_affinity`
- `favorite_categories`
- `regional_proximity`
- `global_ctr`

Их нужно вычислять из raw logs.

## Правила Для Frontend

Frontend должен:
- всегда передавать `session_id`, если действие связано с конкретной выдачей
- передавать `rank_position` и `results_page`, если событие связано с выдачей
- передавать `page_type`
- не отправлять derived metrics как raw event, если их можно посчитать на backend

Frontend не должен:
- сам считать глобальные фичи
- сам вычислять affinity к поставщику
- хранить event log локально как источник истины

## Правила Для Backend

Backend должен:
- обогащать события `supplier_id` и `category_id` по `ste_id`, если фронт их не передал
- держать `Postgres` источником истины
- позволять batch-ingestion для высокочастотных событий
- хранить `search_impressions` отдельно от бизнес-таблиц

Backend не должен:
- затирать старые события
- превращать raw log только в одну таблицу агрегатов без сохранения первички

## Что Передавать ML-Инженерам

Минимальный пакет:
- `search_sessions`
- `search_events`
- `search_impressions`
- `favorites`
- `comparison_items`
- `cart_items`
- `purchase_history`
- `ste_items`
- `suppliers`
- `categories`

Отдельно важно передавать словарь семантики:
- `event_type`
- описание события
- обязательные поля `payload`
- источники на frontend/backend

Готовые примеры формата лежат в:
- [examples/search_events.sample.jsonl](./examples/search_events.sample.jsonl)
- [examples/search_impressions.sample.csv](./examples/search_impressions.sample.csv)
- [examples/user_item_features.sample.csv](./examples/user_item_features.sample.csv)

## Примеры Экспорта

### Search events JSONL

Формат:
- одна JSON-строка на одно событие
- подходит для parquet/jsonl ingestion в ML pipeline

Смотри:
- [examples/search_events.sample.jsonl](./examples/search_events.sample.jsonl)

### Search impressions CSV

Формат:
- одна строка на один показ результата
- удобно для первичного CTR и label engineering

Смотри:
- [examples/search_impressions.sample.csv](./examples/search_impressions.sample.csv)

### Derived features CSV

Формат:
- одна строка на связку `user_id + ste_id`
- подходит для первичного LTR feature store и offline training

Смотри:
- [examples/user_item_features.sample.csv](./examples/user_item_features.sample.csv)

Типичные колонки:
- `click_count`
- `open_count`
- `favorite_count`
- `compare_count`
- `cart_add_count`
- `cart_remove_count`
- `purchase_count`
- `avg_dwell_ms`
- `pogo_count`
- `last_action_at`

## Минимальный ML-Ready Набор

Если нужен самый полезный подмножество данных для LTR:
- `search_impression`
- `result_clicked`
- `result_opened`
- `favorite_added`
- `comparison_added`
- `cart_added`
- `cart_removed`
- `purchase_completed`
- `filter_applied`
- `filters_cleared`
- `quick_back`

## Следующие Рекомендуемые Шаги

1. Добавить nightly aggregation job для user/item/supplier/category features.
2. Зафиксировать экспорт таблиц агрегатов для ML.
3. Версионировать event schema при появлении новых типов событий.
4. Добавить data-quality checks:
   - доля `search_sessions` без `impressions`
   - доля `result_clicked` без `result_opened`
   - доля `purchase_completed` без соответствующего `cart_added`
