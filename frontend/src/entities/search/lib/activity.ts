export type ActivityFilter = 'all' | 'search' | 'shortlist' | 'cart' | 'purchase' | 'feedback'

const SEARCH_EVENT_TYPES = new Set([
  'search_submitted',
  'search_results_rendered',
  'search_refined',
  'suggestion_clicked',
  'result_clicked',
  'result_opened',
  'result_opened_new_tab',
  'filter_applied',
  'filter_removed',
  'filters_cleared',
  'sort_changed',
])

const SHORTLIST_EVENT_TYPES = new Set([
  'favorite_added',
  'favorite_removed',
  'comparison_added',
  'comparison_removed',
])

const CART_EVENT_TYPES = new Set([
  'cart_added',
  'cart_removed',
  'cart_quantity_changed',
  'purchase_intent',
])

const PURCHASE_EVENT_TYPES = new Set(['purchase_completed'])

const FEEDBACK_EVENT_TYPES = new Set(['item_copy', 'irrelevant_marked'])

export function getActivityFilterKey(eventType: string): ActivityFilter {
  if (SEARCH_EVENT_TYPES.has(eventType)) {
    return 'search'
  }
  if (SHORTLIST_EVENT_TYPES.has(eventType)) {
    return 'shortlist'
  }
  if (CART_EVENT_TYPES.has(eventType)) {
    return 'cart'
  }
  if (PURCHASE_EVENT_TYPES.has(eventType)) {
    return 'purchase'
  }
  if (FEEDBACK_EVENT_TYPES.has(eventType)) {
    return 'feedback'
  }
  return 'all'
}

export function getActivityColor(eventType: string) {
  const filterKey = getActivityFilterKey(eventType)
  if (filterKey === 'purchase' || eventType === 'purchase_intent') {
    return 'green'
  }
  if (filterKey === 'shortlist' || eventType === 'result_opened') {
    return 'blue'
  }
  if (filterKey === 'search') {
    return 'processing'
  }
  if (filterKey === 'feedback') {
    return 'volcano'
  }
  return 'default'
}

export const activityFilterOptions: Array<{ value: ActivityFilter; label: string }> = [
  { value: 'all', label: 'Все действия' },
  { value: 'search', label: 'Поиск' },
  { value: 'shortlist', label: 'Shortlist' },
  { value: 'cart', label: 'Корзина' },
  { value: 'purchase', label: 'Закупка' },
  { value: 'feedback', label: 'Обратная связь' },
]
