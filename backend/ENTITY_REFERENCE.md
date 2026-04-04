# Справочник Сущностей И Полей

Этот документ нужен как быстрый reference по backend-сущностям:

- какие таблицы и API-схемы есть в проекте
- какие поля у них есть
- что каждое поле означает
- где это обычно используется

Source of truth:

- таблицы БД: `backend/app/db/models.py`
- API/transport схемы: `backend/app/domain/**/schemas.py`

## Как читать

- `DB сущность` = как данные лежат в PostgreSQL
- `API сущность` = как данные ходят между backend и frontend/debug tooling
- часть количественных полей в БД хранится как `str`, потому что так их проще импортировать из CSV и не терять исходный формат

## DB Сущности

### `OrganizationModel`

| Поле | Что означает |
| --- | --- |
| `id` | Стабильный идентификатор организации |
| `name` | Человекочитаемое название организации |

### `UserModel`

| Поле | Что означает |
| --- | --- |
| `id` | Стабильный идентификатор пользователя |
| `organization_id` | Организация, к которой привязан пользователь |
| `name` | Отображаемое имя пользователя |
| `role` | Роль в продукте, обычно `customer` или `supplier` |

### `CategoryModel`

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор категории каталога |
| `name` | Название категории |
| `parent_id` | Родительская категория для иерархии |

### `SupplierModel`

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор поставщика |
| `name` | Название поставщика |

### `STEItemModel`

Базовая карточка каталога СТЕ.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор СТЕ |
| `title` | Название позиции |
| `description` | Текстовое описание позиции |
| `category_id` | Категория позиции |
| `supplier_id` | Поставщик позиции |
| `attributes_json` | Нормализованные атрибуты позиции в формате `ключ -> значение` |
| `status` | Статус позиции, например `active` |
| `updated_at` | Когда карточка последний раз обновлялась |

### `PurchaseHistoryModel`

История уже совершенных закупок пользователя.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор записи истории |
| `user_id` | Пользователь, для которого зафиксирована закупка |
| `organization_id` | Организация закупки |
| `ste_id` | Какая позиция была куплена |
| `quantity` | Количество, хранится строкой |
| `price` | Цена, хранится строкой |
| `purchased_at` | Дата и время покупки |

### `SearchSessionModel`

Одна поисковая сессия, привязанная к исходному запросу.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор поисковой сессии |
| `user_id` | Кто выполнил поиск |
| `organization_id` | От какой организации шел поиск |
| `query` | Исходный текст запроса |
| `normalized_query` | Нормализованный запрос после preprocessing |
| `created_at` | Когда сессия была создана |

### `SearchEventModel`

Сырым слоем хранит пользовательские события вокруг поиска и карточек.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор события |
| `session_id` | К какой поисковой сессии относится событие |
| `user_id` | Кто сгенерировал событие |
| `organization_id` | Организация пользователя |
| `role` | Роль пользователя на момент события |
| `event_type` | Тип события, например `search_submitted`, `result_clicked`, `cart_added` |
| `ste_id` | Какая позиция СТЕ участвовала в событии, если применимо |
| `supplier_id` | Поставщик, если событие связано с ним |
| `category_id` | Категория, если событие связано с ней |
| `query_text` | Исходный текст запроса в момент события |
| `normalized_query` | Нормализованный текст запроса |
| `corrected_query` | Исправленный текст запроса после spell correction |
| `page_type` | Тип экрана, например каталог или карточка товара |
| `page_url` | URL экрана в момент события |
| `referrer` | Источник перехода, если он был |
| `rank_position` | Позиция результата в выдаче, если событие связано с результатом |
| `results_page` | Номер страницы выдачи |
| `payload_json` | Дополнительные event-specific поля |
| `created_at` | Когда событие было записано |

### `SearchImpressionModel`

Хранит факт показа результата в выдаче.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор impression |
| `search_session_id` | Поисковая сессия, в которой был показ |
| `user_id` | Кому показали результат |
| `organization_id` | Организация пользователя |
| `ste_id` | Какую позицию показали |
| `supplier_id` | Поставщик показанной позиции |
| `category_id` | Категория показанной позиции |
| `rank_position` | Позиция в выдаче |
| `results_page` | Номер страницы результатов |
| `visible` | Результат реально был видим пользователю или нет |
| `rendered_at` | Когда impression был зафиксирован |

### `FavoriteModel`

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор записи избранного |
| `user_id` | Пользователь |
| `ste_id` | Выбранная позиция |
| `created_at` | Когда добавили в избранное |

Ограничение: один и тот же `ste_id` нельзя добавить в избранное одному пользователю дважды.

### `ComparisonItemModel`

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор записи сравнения |
| `user_id` | Пользователь |
| `ste_id` | Сравниваемая позиция |
| `created_at` | Когда позицию добавили в сравнение |

### `CartItemModel`

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор записи корзины |
| `user_id` | Пользователь |
| `ste_id` | Позиция в корзине |
| `quantity` | Количество в корзине, хранится строкой |
| `created_at` | Когда позицию добавили в корзину |
| `updated_at` | Когда количество или запись менялись последний раз |

### `SynonymModel`

Справочник поисковых синонимов.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор записи |
| `term` | Исходный термин |
| `synonym` | Эквивалент или расширение термина |
| `weight` | Вес синонима, хранится строкой |
| `source` | Источник записи, например `manual` |

### `SpellCorrectionModel`

Словарь ручных исправлений.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор записи |
| `wrong_term` | Ошибочный вариант |
| `correct_term` | Исправленный вариант |
| `source` | Источник исправления |

### `UserSearchProfileModel`

Персональный поисковый профиль пользователя.

| Поле | Что означает |
| --- | --- |
| `user_id` | Пользователь, для которого хранится профиль |
| `organization_id` | Его организация |
| `top_categories_json` | Категории, к которым пользователь чаще всего тяготеет |
| `recent_ste_ids_json` | Недавние позиции, с которыми пользователь взаимодействовал |
| `top_suppliers_json` | Наиболее часто встречающиеся поставщики |
| `popular_queries_json` | Повторяющиеся запросы пользователя |
| `updated_at` | Когда профиль был пересобран |

### `OrgSearchProfileModel`

Организационный, а не персональный поисковый профиль.

| Поле | Что означает |
| --- | --- |
| `organization_id` | Организация |
| `top_categories_json` | Главные категории организации |
| `popular_ste_ids_json` | Популярные СТЕ по организации |
| `updated_at` | Когда профиль был пересобран |

## API Сущности

### Auth

#### `DemoUserRead`

Карточка пользователя на экране demo-авторизации.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор demo-пользователя |
| `name` | Имя в UI |
| `organization_id` | Организация пользователя |
| `organization_name` | Название организации |
| `role` | Роль `customer` или `supplier` |
| `persona` | Текстовая persona для демо-сценария |
| `entry_mode` | Режим входа: пустой кабинет, контекст, история |
| `has_history` | Есть ли уже накопленная история |
| `entry_note` | Пояснение для UI про состояние этого пользователя |

#### `DemoLoginRequest`

| Поле | Что означает |
| --- | --- |
| `user_id` | Каким demo-пользователем войти |

#### `AuthSessionRead`

Сессия, которую frontend хранит локально после логина.

| Поле | Что означает |
| --- | --- |
| `user_id` | Пользователь в текущей сессии |
| `name` | Имя пользователя |
| `organization_id` | Организация |
| `organization_name` | Название организации |
| `role` | Роль пользователя |
| `entry_mode` | Режим стартового состояния |
| `has_history` | Есть ли накопленная история |
| `entry_note` | Короткое пояснение про начальное состояние |
| `persona` | Persona для demo/onboarding |

### Catalog

#### `CategoryRead`

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор категории |
| `name` | Название категории |
| `parent_id` | Родительская категория |

#### `SupplierRead`

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор поставщика |
| `name` | Название поставщика |

#### `CatalogSummaryRead`

Общий summary каталога и пользовательского состояния.

| Поле | Что означает |
| --- | --- |
| `ste_items_count` | Сколько всего позиций СТЕ в каталоге |
| `categories_count` | Сколько категорий в каталоге |
| `suppliers_count` | Сколько поставщиков в каталоге |
| `purchase_history_count` | Сколько записей истории закупок загружено |
| `favorites_count` | Сколько позиций в избранном у текущего пользователя |
| `comparison_count` | Сколько позиций в сравнении |
| `cart_count` | Сколько позиций в корзине |
| `latest_item_updated_at` | Последнее обновление каталога |
| `top_categories` | Самые крупные категории по количеству позиций |

#### `SupplierInsightsRead`

Supplier dashboard summary.

| Поле | Что означает |
| --- | --- |
| `matched_suppliers` | Поставщики, пересекающиеся с текущим supplier-контуром |
| `owned_catalog_items_count` | Сколько позиций ассортимента относится к сегменту |
| `owned_purchase_history_count` | Сколько исторических закупок относится к этому сегменту |
| `tracked_categories_count` | Сколько категорий dashboard сейчас реально отслеживает |
| `top_demand_categories` | Категории с наибольшим спросом |
| `top_competitors` | Основные конкуренты |
| `hot_opportunities` | Конкретные позиции с заметным спросом |

#### `STEItemRead`

Базовая transport-схема позиции каталога.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор СТЕ |
| `title` | Название позиции |
| `description` | Описание |
| `category_id` | Идентификатор категории |
| `category_name` | Человекочитаемое название категории |
| `supplier_id` | Идентификатор поставщика |
| `supplier_name` | Название поставщика |
| `attributes` | Нормализованные атрибуты товара |
| `status` | Статус позиции |

#### `SearchableSTEItemRead`

Расширенная версия `STEItemRead` для search/debug.

| Поле | Что означает |
| --- | --- |
| `retrieval_score` | Сводный retrieval score до финального ранжирования |
| `retrieval_reasons` | Причины попадания в candidate set |
| `retrieval_channel_scores` | Оценки по retrieval-каналам |
| `retrieval_channel_ranks` | Позиции по каналам |
| `retrieval_features` | Features, которые видит ranking/debug слой |

#### `RelatedSTEItemRead`

Похожая позиция для product page.

| Поле | Что означает |
| --- | --- |
| `score` | Оценка похожести или релевантности |
| `reasons` | Объяснения, почему позиция показана |

#### `PurchaseHistoryItemRead`

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор записи истории |
| `ste_id` | Купленная позиция |
| `title` | Название позиции |
| `description` | Описание позиции |
| `category_id` | Категория |
| `category_name` | Название категории |
| `supplier_id` | Поставщик |
| `supplier_name` | Название поставщика |
| `quantity` | Количество |
| `price` | Цена |
| `purchased_at` | Дата закупки |

#### `CatalogFeedRead`

Стартовая лента без явного поискового запроса.

| Поле | Что означает |
| --- | --- |
| `items` | Позиции стартовой ленты |
| `total` | Всего доступно позиций |
| `limit` | Текущий лимит выдачи |
| `offset` | Текущий offset |

### Search

#### `CurrentActor`

Контекст текущего пользователя для search pipeline.

| Поле | Что означает |
| --- | --- |
| `user_id` | Пользователь |
| `organization_id` | Организация |
| `role` | Роль пользователя |
| `name` | Имя пользователя |
| `organization_name` | Название организации |
| `personalization_enabled` | Включать ли персонализацию в расчете выдачи |

#### `SearchFilters`

| Поле | Что означает |
| --- | --- |
| `category_id` | Ограничить поиск категорией |
| `supplier_id` | Ограничить поиск поставщиком |
| `strict_match` | Использовать более строгий матчинг |

#### `SearchRequest`

| Поле | Что означает |
| --- | --- |
| `query` | Текст запроса |
| `filters` | Фильтры поиска |

#### `CandidateItem`

Позиция в search response.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор СТЕ |
| `title` | Название |
| `category` | Название категории |
| `supplier` | Название поставщика |
| `description` | Описание |
| `score` | Финальный score, который видит пользователь |
| `reasons` | Explainability-объяснения для UI |

Служебные поля, скрытые из обычного API-ответа, но живущие в объекте:

- `category_id`, `supplier_id`, `status`, `attributes`
- `baseline_score`, `retrieval_score`
- `retrieval_reasons`, `retrieval_channel_scores`, `retrieval_channel_ranks`
- `retrieval_features`

#### `SearchMeta`

Метаданные ответа поиска.

| Поле | Что означает |
| --- | --- |
| `session_id` | Идентификатор search session, если запрос был записан |
| `query` | Исходный запрос |
| `normalized_query` | Нормализованный запрос |
| `corrected_query` | Исправленный запрос |
| `applied_synonyms` | Синонимы, подмешанные в запрос |
| `synonym_sources` | Источник каждого примененного синонима |
| `synonym_confidence` | Вес/уверенность по синонимам |
| `explanations` | Короткие текстовые explainability-подсказки |
| `ranking_mode` | Какой ranking mode использовался |

#### `SearchSuggestion` и `SearchSuggestionsResponse`

Используются для autocomplete.

| Поле | Что означает |
| --- | --- |
| `label` | Текст подсказки |
| `type` | Тип подсказки |
| `group` | Группа подсказки |
| `description` | Дополнительное пояснение |

Метаданные suggestions:

- `query` - исходный запрос
- `normalized_query` - нормализованный запрос
- `effective_query` - финальный текст, по которому строились suggestions
- `corrected_query` - исправление, если было
- `correction_type` - тип исправления

#### `SearchSessionRead` и `SearchHistoryResponse`

История поисковых запросов пользователя.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор search session |
| `query` | Исходный запрос |
| `normalized_query` | Нормализованный запрос |
| `created_at` | Когда запрос выполнялся |

#### `SearchActivityItemRead` и `SearchActivityResponse`

Нормализованная activity-лента для UI.

| Поле | Что означает |
| --- | --- |
| `id` | Идентификатор события |
| `session_id` | Поисковая сессия, к которой привязано действие |
| `event_type` | Тип действия |
| `title` | Короткий заголовок для UI |
| `description` | Поясняющий текст для UI |
| `ste_id` | Позиция, если действие относится к товару |
| `ste_title` | Название позиции |
| `page_type` | Тип экрана |
| `query` | Поисковый запрос, если релевантно |
| `created_at` | Когда действие произошло |

#### Debug search entities

`SearchDebugResponse` разбит на 4 блока:

- `query` - как backend понял запрос
- `profile` - какой профиль был использован
- `ranking` - какой ranking provider и fallback сработали
- `candidates` - финальный candidate set с baseline/retrieval/final score

Особенно полезные поля:

- `SearchDebugStructuredQueryRead.is_hard_query` - сложный ли запрос
- `SearchDebugCandidateRead.baseline_score` - baseline score до ML
- `SearchDebugCandidateRead.retrieval_features` - feature dump для ML/debug
- `SearchDebugRankingRead.fallback_to_baseline` - пришлось ли откатиться на baseline

#### `SpellcheckResponse`

| Поле | Что означает |
| --- | --- |
| `original_query` | Исходный запрос |
| `corrected_query` | Исправленный запрос или `null` |

#### `SearchStackStatusRead`

Сводное состояние поиска и ranking stack после старта.

| Поле | Что означает |
| --- | --- |
| `ready` | Общая готовность stack |
| `search_warmup` | Статус прогрева retrieval/search слоя |
| `ranking_warmup` | Статус прогрева ranking provider |
| `ranking_provider` | Имя текущего ranking provider |
| `ranking_provider_mode` | Режим provider-а |
| `search_documents_count` | Сколько документов в поисковом индексе |
| `semantic_backend` | Какой semantic backend используется |
| `semantic_faiss_enabled` | Включен ли FAISS |
| `search_warmup_error` | Ошибка прогрева поиска, если была |
| `ranking_warmup_error` | Ошибка прогрева ranking layer, если была |

### Personalization

#### `SearchProfileRead`

Агрегированный профиль, который frontend и debug endpoints видят как единый объект.

| Поле | Что означает |
| --- | --- |
| `user_id` | Пользователь |
| `organization_id` | Организация |
| `top_categories` | Личные top-категории |
| `org_top_categories` | Top-категории организации |
| `recent_ste_ids` | Недавние товарные сигналы |
| `top_suppliers` | Чаще всего встречающиеся поставщики |
| `popular_ste_ids` | Популярные позиции на уровне организации |
| `popular_queries` | Частые запросы пользователя |
| `active_signals` | Готовые текстовые сигналы для UI/explainability |

### User Actions

#### Create/Update payloads

| Схема | Поля | Что означает |
| --- | --- | --- |
| `FavoriteCreate` | `ste_id` | Добавить позицию в избранное |
| `ComparisonCreate` | `ste_id` | Добавить позицию в сравнение |
| `CartItemCreate` | `ste_id`, `quantity` | Добавить позицию в корзину |
| `CartItemUpdate` | `quantity` | Изменить количество в корзине |
| `PurchaseCreate` | `ste_id`, `quantity`, `price`, `session_id`, `contract_id` | Зафиксировать покупку |

#### Read models

Все read-модели содержат вложенный `item: STEItemRead`, чтобы frontend мог сразу рисовать карточку.

| Схема | Поля |
| --- | --- |
| `FavoriteItemRead` | `id`, `ste_id`, `created_at`, `item` |
| `ComparisonItemRead` | `id`, `ste_id`, `created_at`, `item` |
| `CartItemRead` | `id`, `ste_id`, `quantity`, `created_at`, `updated_at`, `item` |

### Events / Telemetry

#### `SearchEventCreate`

Payload для записи одного telemetry event.

Ключевые поля:

- `session_id` - search session
- `event_type` - тип события
- `ste_id`, `supplier_id`, `category_id` - привязка к сущности
- `query_text`, `normalized_query`, `corrected_query` - поисковый контекст
- `page_type`, `page_url`, `referrer` - экранный контекст
- `rank_position`, `results_page` - позиция в выдаче
- `payload` - event-specific метаданные

#### `SearchImpressionCreate`

Payload для записи одного показа результата.

| Поле | Что означает |
| --- | --- |
| `search_session_id` | Поисковая сессия |
| `ste_id` | Показанная позиция |
| `supplier_id` | Поставщик |
| `category_id` | Категория |
| `rank_position` | Позиция в выдаче |
| `results_page` | Номер страницы |
| `visible` | Видел ли пользователь карточку реально |

#### `SearchEventRead` и `SearchImpressionRead`

Это уже записанные telemetry-сущности с техническими полями:

- `id`
- `user_id`
- `organization_id`
- временная метка `created_at` или `rendered_at`

#### `TelemetryHealthRead`

Сводное качество telemetry по пользователю.

| Поле | Что означает |
| --- | --- |
| `user_id` | Проверяемый пользователь |
| `search_session_id` | Опционально конкретная сессия |
| `search_sessions_count` | Сколько search sessions найдено |
| `events_count` | Сколько событий найдено |
| `impressions_count` | Сколько impressions найдено |
| `result_clicked_count` | Сколько кликов по результатам |
| `result_opened_count` | Сколько открытий карточек |
| `purchase_intent_count` | Сколько сигналов намерения купить |
| `purchase_completed_count` | Сколько завершенных покупок |
| `search_sessions_with_impressions_count` | Сколько сессий имеют impressions |
| `search_sessions_without_impressions_count` | Сколько сессий без impressions |
| `click_through_rate` | CTR по telemetry |
| `open_after_click_rate` | Доля открытий после клика |
| `purchase_after_intent_rate` | Доля покупок после сигнала намерения |
| `event_counts` | Разбивка количества по типам событий |

## Что полезно знать отдельно

### Какие сущности чаще всего важны frontend

- `AuthSessionRead`
- `CatalogSummaryRead`
- `STEItemRead`
- `SearchResponse`
- `SearchProfileRead`
- `SearchActivityResponse`
- `FavoriteItemRead`, `ComparisonItemRead`, `CartItemRead`

### Какие сущности чаще всего важны ML/debug

- `SearchSessionModel`
- `SearchEventModel`
- `SearchImpressionModel`
- `UserSearchProfileModel`
- `OrgSearchProfileModel`
- `SearchDebugResponse`
- `SearchStackStatusRead`

### Где смотреть event-типизацию

Список допустимых `event_type` живет в `backend/app/domain/events/schemas.py` в `EventType`.
