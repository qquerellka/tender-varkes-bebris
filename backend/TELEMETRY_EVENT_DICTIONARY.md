# Telemetry Event Dictionary

Этот документ фиксирует словарь raw events для frontend, backend и handoff в ML-команду.

Связанные документы:
- [TELEMETRY_SPEC.md](/home/qquerell/programming/frontend-template/my-app/backend/TELEMETRY_SPEC.md)
- [ML_HANDOFF.md](/home/qquerell/programming/frontend-template/my-app/backend/ML_HANDOFF.md)

## Формат События

Общие поля почти для всех событий:
- `session_id`
- `event_type`
- `ste_id`
- `page_type`
- `rank_position`
- `results_page`
- `query_text`
- `normalized_query`
- `corrected_query`
- `payload`

Контекст пользователя и организации backend добавляет сам:
- `user_id`
- `organization_id`
- `role`

## Search Events

| Event | Когда отправляется | Минимальный payload |
|---|---|---|
| `search_submitted` | backend создал новую search session | `filters`, `sort_by` |
| `search_results_rendered` | frontend отрисовал выдачу | `results_count`, `top_ste_ids` |
| `search_refined` | пользователь сменил запрос после предыдущей выдачи | `next_query` |
| `search_abandoned` | пользователь ушёл в новый запрос без meaningful interaction | `next_query` |
| `suggestion_clicked` | пользователь выбрал search suggestion | `label`, `source` |

## Impression Events

| Event | Когда отправляется | Минимальный payload |
|---|---|---|
| `search_impression` | карточка показана в выдаче | `visible` |

Примечание:
сами показы хранятся в `search_impressions`, а не только в `search_events`.

## Result Interaction

| Event | Когда отправляется | Минимальный payload |
|---|---|---|
| `result_clicked` | обычный клик по карточке из каталога | `score` optional |
| `result_opened` | карточка реально открылась | `source` |
| `result_opened_new_tab` | карточка открыта в новой вкладке | `score` optional |

## Product Detail

| Event | Когда отправляется | Минимальный payload |
|---|---|---|
| `product_view_started` | карточка товара открыта и начат просмотр | пустой payload |
| `product_view_ended` | пользователь покинул карточку | `dwell_ms` |
| `quick_back` | карточка закрыта слишком быстро | `dwell_ms` |
| `item_copy` | пользователь скопировал текст с карточки | `selection_length`, `copied_text` |
| `irrelevant_marked` | пользователь явно отметил позицию как нерелевантную | `source`, `source_tab` optional |

## Collections And Intent

| Event | Когда отправляется | Минимальный payload |
|---|---|---|
| `favorite_added` | товар добавлен в избранное | пустой payload |
| `favorite_removed` | товар удалён из избранного | пустой payload |
| `comparison_added` | товар добавлен в сравнение | пустой payload |
| `comparison_removed` | товар удалён из сравнения | пустой payload |
| `compare_viewed` | открыт экран сравнения | `compare_count`, `ste_ids` |
| `cart_added` | товар добавлен в корзину | `quantity` |
| `cart_removed` | товар удалён из корзины | `quantity` optional |
| `cart_quantity_changed` | количество в корзине изменено | `previous_quantity`, `next_quantity` |
| `purchase_intent` | пользователь явно показывает намерение купить | `items_count`, `total_quantity`, `unique_categories`, `unique_suppliers` |
| `purchase_completed` | покупка/черновик закупки завершены | `quantity`, `price`, `contract_id` |

## Filters And Controls

| Event | Когда отправляется | Минимальный payload |
|---|---|---|
| `filter_applied` | фильтр включён | `filter_name`, `filter_value` |
| `filter_removed` | фильтр снят | `filter_name`, `filter_value` |
| `filters_cleared` | нажата кнопка сброса фильтров | `category_id`, `supplier_id`, `strict_match` |
| `sort_changed` | пользователь сменил сортировку | `previous_sort`, `next_sort` |
| `scroll_depth_changed` | достигнут порог скролла выдачи | `depth_percent`, `visible_results` |

## Реально Используется Сейчас

В текущем UI уже реально отправляются:
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

## Что Не Является Raw Event

Нельзя передавать как primary source of truth:
- `dwell_time`
- `pogo_sticking`
- `impressions_without_clicks`
- `user_supplier_affinity`
- `favorite_categories`
- `regional_proximity`
- `global_ctr`

Это производные признаки, которые ML-команда считает из сырого telemetry-слоя.
