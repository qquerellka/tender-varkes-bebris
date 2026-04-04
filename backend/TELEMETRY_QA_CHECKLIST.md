# Telemetry QA Checklist

Этот документ нужен для ручной проверки telemetry без прямого доступа к БД.

Проверка идёт через debug-ручки:
- `GET /api/v1/debug/telemetry/events`
- `GET /api/v1/debug/telemetry/impressions`

Заголовок для demo-пользователя:

```text
X-Demo-User-Id: <demo_user_id>
```

Полезные query params:
- `user_id`
- `search_session_id`
- `limit`

## Готовые Curl Примеры

Подставь свой backend host и demo-user:

```bash
export API_BASE="http://127.0.0.1:8000"
export DEMO_USER_ID="demo_customer_office"
export SEARCH_SESSION_ID="<search_session_id>"
```

Последние события пользователя:

```bash
curl -sS \
  -H "X-Demo-User-Id: ${DEMO_USER_ID}" \
  "${API_BASE}/api/v1/debug/telemetry/events?limit=20"
```

Последние impressions пользователя:

```bash
curl -sS \
  -H "X-Demo-User-Id: ${DEMO_USER_ID}" \
  "${API_BASE}/api/v1/debug/telemetry/impressions?limit=20"
```

События по конкретной search session:

```bash
curl -sS \
  -H "X-Demo-User-Id: ${DEMO_USER_ID}" \
  "${API_BASE}/api/v1/debug/telemetry/events?search_session_id=${SEARCH_SESSION_ID}&limit=50"
```

Impressions по конкретной search session:

```bash
curl -sS \
  -H "X-Demo-User-Id: ${DEMO_USER_ID}" \
  "${API_BASE}/api/v1/debug/telemetry/impressions?search_session_id=${SEARCH_SESSION_ID}&limit=50"
```

Только типы последних событий:

```bash
curl -sS \
  -H "X-Demo-User-Id: ${DEMO_USER_ID}" \
  "${API_BASE}/api/v1/debug/telemetry/events?limit=20" \
  | jq -r '.items[] | [.created_at, .event_type, .ste_id] | @tsv'
```

Только impressions с позициями:

```bash
curl -sS \
  -H "X-Demo-User-Id: ${DEMO_USER_ID}" \
  "${API_BASE}/api/v1/debug/telemetry/impressions?search_session_id=${SEARCH_SESSION_ID}&limit=20" \
  | jq -r '.items[] | [.rendered_at, .ste_id, .rank_position, .results_page] | @tsv'
```

## Базовый Порядок Проверки

1. Войти под demo-user.
2. Выполнить действие в UI.
3. Открыть debug-ручку для `events` или `impressions`.
4. Проверить, что нужный `event_type` появился сверху списка.

## Быстрые Debug URL

```text
/api/v1/debug/telemetry/events?limit=20
/api/v1/debug/telemetry/impressions?limit=20
/api/v1/debug/telemetry/events?search_session_id=<session_id>&limit=50
/api/v1/debug/telemetry/impressions?search_session_id=<session_id>&limit=50
```

## Сценарии

### 1. Поиск

UI:
- ввести запрос в каталог
- нажать Enter или кнопку поиска

Ожидаем:
- `search_submitted`
- `search_results_rendered`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?limit=20`

### 2. Показы результатов

UI:
- выполнить поиск с непустой выдачей

Ожидаем:
- записи в `search_impressions`

Где смотреть:
- `GET /api/v1/debug/telemetry/impressions?search_session_id=<session_id>&limit=20`

Что проверить:
- `rank_position`
- `ste_id`
- `results_page`

### 3. Выбор search suggestion

UI:
- начать вводить запрос
- выбрать подсказку из autocomplete

Ожидаем:
- `suggestion_clicked`
- затем новая `search_submitted/search_results_rendered` цепочка

Где смотреть:
- `GET /api/v1/debug/telemetry/events?limit=20`

### 4. Клик по карточке из каталога

UI:
- выполнить поиск
- открыть карточку кликом

Ожидаем:
- `result_clicked`
- `result_opened`
- `product_view_started`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?search_session_id=<session_id>&limit=20`

### 5. Открытие в новой вкладке

UI:
- middle click по карточке или по заголовку карточки

Ожидаем:
- `result_opened_new_tab`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?search_session_id=<session_id>&limit=20`

### 6. Долгое и короткое чтение карточки

UI:
- открыть карточку
- подождать и уйти назад

Ожидаем:
- `product_view_ended`

Дополнительно:
- если уйти быстрее примерно чем за 5 секунд, ожидаем `quick_back`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?search_session_id=<session_id>&limit=20`

Что проверить в payload:
- `dwell_ms`

### 7. Copy event

UI:
- открыть карточку
- выделить текст и скопировать

Ожидаем:
- `item_copy`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?search_session_id=<session_id>&limit=20`

Что проверить в payload:
- `selection_length`
- `copied_text`

### 8. Избранное

UI:
- добавить позицию в избранное
- затем удалить

Ожидаем:
- `favorite_added`
- `favorite_removed`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?limit=20`

### 9. Сравнение

UI:
- добавить позицию в сравнение
- открыть вкладку сравнения
- удалить позицию из сравнения

Ожидаем:
- `comparison_added`
- `compare_viewed`
- `comparison_removed`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?limit=20`

### 10. Корзина

UI:
- добавить товар в корзину
- изменить количество
- удалить товар

Ожидаем:
- `cart_added`
- `cart_quantity_changed`
- `cart_removed`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?limit=20`

### 11. Purchase intent и purchase completed

UI:
- открыть корзину
- нажать `Оформить закупку`

Ожидаем:
- `purchase_intent`
- `purchase_completed`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?limit=20`

### 12. Фильтры

UI:
- выбрать категорию
- выбрать поставщика
- включить strict match
- снять фильтр
- нажать `Сбросить фильтры`

Ожидаем:
- `filter_applied`
- `filter_removed`
- `filters_cleared`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?search_session_id=<session_id>&limit=30`

### 13. Сортировка

UI:
- выполнить поиск
- сменить сортировку в header блока результатов

Ожидаем:
- `sort_changed`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?search_session_id=<session_id>&limit=20`

Что проверить в payload:
- `previous_sort`
- `next_sort`

### 14. Скролл

UI:
- выполнить поиск
- прокрутить страницу вниз

Ожидаем:
- `scroll_depth_changed`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?search_session_id=<session_id>&limit=30`

Что проверить в payload:
- `depth_percent`
- `visible_results`

### 15. Негативный сигнал

UI:
- нажать `Нерелевантно` на карточке в каталоге или на отдельной product page

Ожидаем:
- `irrelevant_marked`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?limit=20`

### 16. Refine и abandon

UI:
- выполнить один поиск
- ничего полезного не кликать
- ввести новый запрос

Ожидаем:
- `search_refined`
- `search_abandoned`

Где смотреть:
- `GET /api/v1/debug/telemetry/events?limit=20`

## Что Считать OK

Проверка считается успешной, если:
- нужный `event_type` появляется в debug-ручке
- `session_id` соответствует реальной search session
- `ste_id` заполнен для item-level событий
- `payload` содержит ожидаемые служебные поля

## Что Пока Не Надо Проверять Как Raw Event

Это не первичные события, а derived logic:
- `dwell_time`
- `pogo_sticking`
- `impressions_without_clicks`
- supplier affinity
- favorite categories
- regional proximity
