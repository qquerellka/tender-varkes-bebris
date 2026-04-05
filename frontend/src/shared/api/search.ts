import axios from 'axios'

export type SearchFilters = {
  strict_match: boolean
  category_id?: string
  supplier_id?: string
}

export type ActorContext = {
  userId: string
}

export type DemoUser = {
  id: string
  name: string
  organization_id: string
  organization_name: string
  role: string
  persona: string
  entry_mode?: string
  has_history?: boolean
  entry_note?: string | null
}

export type AuthSession = {
  user_id: string
  name: string
  organization_id: string
  organization_name: string
  role: string
  entry_mode?: string
  has_history?: boolean
  entry_note?: string | null
  persona?: string | null
}

export type SearchItem = {
  id: string
  title: string
  category: string
  supplier: string
  description: string
  score: number
  reasons: string[]
}

export type SearchQueryVariant = {
  query: string
  source: string
  confidence: string
  is_primary: boolean
}

export type SearchResponse = {
  items: SearchItem[]
  meta: {
    session_id: string
    query: string
    normalized_query: string
    corrected_query: string | null
    correction_confidence?: string
    applied_synonyms: string[]
    query_variants?: SearchQueryVariant[]
    explanations: string[]
    ranking_mode: string
  }
}

export type SearchHistoryItem = {
  id: string
  query: string
  normalized_query: string
  created_at: string
}

export type SearchHistoryResponse = {
  items: SearchHistoryItem[]
}

export type SearchActivityItem = {
  id: string
  session_id: string
  event_type: SearchEventType | string
  title: string
  description: string
  ste_id?: string | null
  ste_title?: string | null
  page_type?: string | null
  query?: string | null
  created_at: string
}

export type SearchActivityResponse = {
  items: SearchActivityItem[]
}

export type SearchSuggestion = {
  label: string
  type: string
  group: string
  description?: string | null
}

export type SearchSuggestionsResponse = {
  items: SearchSuggestion[]
  meta: {
    query: string
    normalized_query: string
    effective_query: string
    corrected_query: string | null
    correction_type: string
    correction_confidence?: string
    query_variants?: SearchQueryVariant[]
  }
}

export type SearchProfileResponse = {
  user_id: string
  organization_id: string
  top_categories: string[]
  org_top_categories: string[]
  recent_ste_ids: string[]
  top_suppliers: string[]
  popular_ste_ids: string[]
  popular_queries: string[]
  active_signals: string[]
}

export type SupplierInsightSupplier = {
  id: string
  name: string
  token_overlap: number
  catalog_items_count: number
  purchase_history_count: number
}

export type SupplierInsightCategory = {
  id: string
  name: string
  purchase_count: number
  catalog_items_count: number
}

export type SupplierInsightOpportunity = {
  ste_id: string
  title: string
  supplier_name: string
  category_name: string
  purchase_count: number
}

export type SupplierInsightsResponse = {
  matched_suppliers: SupplierInsightSupplier[]
  owned_catalog_items_count: number
  owned_purchase_history_count: number
  tracked_categories_count: number
  top_demand_categories: SupplierInsightCategory[]
  top_competitors: SupplierInsightSupplier[]
  hot_opportunities: SupplierInsightOpportunity[]
}

export type CatalogCategory = {
  id: string
  name: string
  parent_id: string | null
}

export type CatalogSupplier = {
  id: string
  name: string
}

export type CatalogSummaryCategory = {
  id: string
  name: string
  item_count: number
}

export type CatalogSummary = {
  ste_items_count: number
  categories_count: number
  suppliers_count: number
  purchase_history_count: number
  favorites_count: number
  comparison_count: number
  cart_count: number
  latest_item_updated_at: string | null
  top_categories: CatalogSummaryCategory[]
}

export type CatalogFeedItem = CatalogItem & {
  feed_reason: string
}

export type CatalogFeedResponse = {
  items: CatalogFeedItem[]
  total: number
  limit: number
  offset: number
}

export type CatalogItem = {
  id: string
  title: string
  description: string
  category_id: string
  category_name: string
  supplier_id: string
  supplier_name: string
  attributes: Record<string, string>
  status: string
}

export type PurchaseHistoryItem = {
  id: string
  ste_id: string
  title: string
  description: string
  category_id: string
  category_name: string
  supplier_id: string
  supplier_name: string
  quantity: string
  price: string
  purchased_at: string
}

export type RelatedSearchItem = CatalogItem & {
  score: number
  reasons: string[]
}

export type FavoriteItem = {
  id: string
  ste_id: string
  created_at: string
  item: CatalogItem
}

export type ComparisonItem = {
  id: string
  ste_id: string
  created_at: string
  item: CatalogItem
}

export type CartItem = {
  id: string
  ste_id: string
  quantity: number
  created_at: string
  updated_at: string
  item: CatalogItem
}

export type TelemetryEvent = {
  id: string
  session_id: string
  user_id: string
  organization_id: string
  role: string
  event_type: SearchEventType
  ste_id?: string | null
  supplier_id?: string | null
  category_id?: string | null
  query_text?: string | null
  normalized_query?: string | null
  corrected_query?: string | null
  page_type?: string | null
  page_url?: string | null
  referrer?: string | null
  rank_position?: number | null
  results_page?: number | null
  payload: Record<string, unknown>
  created_at: string
}

export type TelemetryEventList = {
  items: TelemetryEvent[]
  total: number
}

export type TelemetryImpression = {
  id: string
  search_session_id: string
  user_id: string
  organization_id: string
  ste_id: string
  supplier_id?: string | null
  category_id?: string | null
  rank_position: number
  results_page: number
  visible: boolean
  rendered_at: string
}

export type TelemetryImpressionList = {
  items: TelemetryImpression[]
  total: number
}

export type TelemetryCountByType = {
  key: string
  count: number
}

export type TelemetryHealth = {
  user_id: string
  search_session_id?: string | null
  search_sessions_count: number
  events_count: number
  impressions_count: number
  result_clicked_count: number
  result_opened_count: number
  purchase_intent_count: number
  purchase_completed_count: number
  search_sessions_with_impressions_count: number
  search_sessions_without_impressions_count: number
  click_through_rate: number
  open_after_click_rate: number
  purchase_after_intent_rate: number
  event_counts: TelemetryCountByType[]
}

export type SearchStackStatus = {
  ready: boolean
  search_warmup: string
  ranking_warmup: string
  ranking_provider?: string | null
  ranking_provider_mode?: string | null
  search_documents_count?: number | null
  semantic_backend?: string | null
  semantic_faiss_enabled?: boolean | null
  search_warmup_error?: string | null
  ranking_warmup_error?: string | null
}

export type SearchEventType =
  | 'search_submitted'
  | 'search_results_rendered'
  | 'search_impression'
  | 'suggestion_clicked'
  | 'result_clicked'
  | 'result_opened'
  | 'result_opened_new_tab'
  | 'product_view_started'
  | 'product_view_ended'
  | 'item_copy'
  | 'favorite_added'
  | 'favorite_removed'
  | 'comparison_added'
  | 'comparison_removed'
  | 'compare_viewed'
  | 'cart_added'
  | 'cart_removed'
  | 'cart_quantity_changed'
  | 'filter_applied'
  | 'filter_removed'
  | 'filters_cleared'
  | 'sort_changed'
  | 'purchase_completed'
  | 'quick_back'
  | 'scroll_depth_changed'
  | 'search_refined'
  | 'search_abandoned'
  | 'purchase_intent'
  | 'irrelevant_marked'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  timeout: 30_000,
})

function buildActorConfig(actor: ActorContext) {
  return {
    headers: {
      'X-Demo-User-Id': actor.userId,
    },
  }
}

export async function getDemoUsers(): Promise<DemoUser[]> {
  const { data } = await api.get<DemoUser[]>('/api/v1/auth/demo-users')
  return data
}

export async function loginDemoUser(userId: string): Promise<AuthSession> {
  const { data } = await api.post<AuthSession>('/api/v1/auth/login-demo', {
    user_id: userId,
  })
  return data
}

export async function getMe(actor: ActorContext): Promise<AuthSession> {
  const { data } = await api.get<AuthSession>('/api/v1/auth/me', buildActorConfig(actor))
  return data
}

export async function searchCatalog(payload: {
  query: string
  filters: SearchFilters
  actor: ActorContext
}): Promise<SearchResponse> {
  const { actor, ...requestPayload } = payload
  const { data } = await api.post<SearchResponse>(
    '/api/v1/search',
    requestPayload,
    buildActorConfig(actor),
  )
  return data
}

export async function getSearchHistory(actor: ActorContext): Promise<SearchHistoryResponse> {
  const { data } = await api.get<SearchHistoryResponse>(
    '/api/v1/search/history',
    buildActorConfig(actor),
  )
  return data
}

export async function getSearchActivity(
  actor: ActorContext,
  limit = 12,
): Promise<SearchActivityResponse> {
  const { data } = await api.get<SearchActivityResponse>('/api/v1/search/activity', {
    ...buildActorConfig(actor),
    params: { limit },
  })
  return data
}

export async function getSearchSuggestions(
  query: string,
  actor: ActorContext,
  signal?: AbortSignal,
): Promise<SearchSuggestionsResponse> {
  const { data } = await api.get<SearchSuggestionsResponse>('/api/v1/search/suggestions', {
    ...buildActorConfig(actor),
    params: { query },
    signal,
  })
  return data
}

export async function getSearchProfile(actor: ActorContext): Promise<SearchProfileResponse> {
  const { data } = await api.get<SearchProfileResponse>(
    '/api/v1/profile/search',
    buildActorConfig(actor),
  )
  return data
}

export async function getPurchaseHistory(
  actor: ActorContext,
  limit = 6,
): Promise<PurchaseHistoryItem[]> {
  const { data } = await api.get<PurchaseHistoryItem[]>(
    '/api/v1/profile/purchases',
    {
      ...buildActorConfig(actor),
      params: { limit },
    },
  )
  return data
}

export async function getSupplierInsights(
  actor: ActorContext,
): Promise<SupplierInsightsResponse> {
  const { data } = await api.get<SupplierInsightsResponse>(
    '/api/v1/profile/supplier-insights',
    buildActorConfig(actor),
  )
  return data
}

export async function getCategories(): Promise<CatalogCategory[]> {
  const { data } = await api.get<CatalogCategory[]>('/api/v1/catalog/categories')
  return data
}

export async function getSuppliers(): Promise<CatalogSupplier[]> {
  const { data } = await api.get<CatalogSupplier[]>('/api/v1/catalog/suppliers')
  return data
}

export async function getCatalogSummary(actor: ActorContext): Promise<CatalogSummary> {
  const { data } = await api.get<CatalogSummary>(
    '/api/v1/catalog/summary',
    buildActorConfig(actor),
  )
  return data
}

export async function getCatalogFeed(payload: {
  actor: ActorContext
  limit?: number
  offset?: number
  category_id?: string
  supplier_id?: string
}): Promise<CatalogFeedResponse> {
  const { actor, ...params } = payload
  const { data } = await api.get<CatalogFeedResponse>('/api/v1/catalog/feed', {
    ...buildActorConfig(actor),
    params,
  })
  return data
}

export async function getRelatedItems(steId: string, limit = 4): Promise<RelatedSearchItem[]> {
  const { data } = await api.get<RelatedSearchItem[]>(`/api/v1/catalog/ste/${steId}/related`, {
    params: { limit },
  })
  return data
}

export async function getCatalogItem(steId: string): Promise<CatalogItem> {
  const { data } = await api.get<CatalogItem>(`/api/v1/catalog/ste/${steId}`)
  return data
}

export async function getFavorites(actor: ActorContext): Promise<FavoriteItem[]> {
  const { data } = await api.get<FavoriteItem[]>('/api/v1/actions/favorites', buildActorConfig(actor))
  return data
}

export async function addFavorite(steId: string, actor: ActorContext): Promise<FavoriteItem> {
  const { data } = await api.post<FavoriteItem>(
    '/api/v1/actions/favorites',
    { ste_id: steId },
    buildActorConfig(actor),
  )
  return data
}

export async function removeFavorite(steId: string, actor: ActorContext): Promise<void> {
  await api.delete(`/api/v1/actions/favorites/${steId}`, buildActorConfig(actor))
}

export async function getComparisonItems(actor: ActorContext): Promise<ComparisonItem[]> {
  const { data } = await api.get<ComparisonItem[]>('/api/v1/actions/compare', buildActorConfig(actor))
  return data
}

export async function addComparisonItem(
  steId: string,
  actor: ActorContext,
): Promise<ComparisonItem> {
  const { data } = await api.post<ComparisonItem>(
    '/api/v1/actions/compare',
    { ste_id: steId },
    buildActorConfig(actor),
  )
  return data
}

export async function removeComparisonItem(
  steId: string,
  actor: ActorContext,
): Promise<void> {
  await api.delete(`/api/v1/actions/compare/${steId}`, buildActorConfig(actor))
}

export async function getCartItems(actor: ActorContext): Promise<CartItem[]> {
  const { data } = await api.get<CartItem[]>('/api/v1/actions/cart', buildActorConfig(actor))
  return data
}

export async function addCartItem(
  steId: string,
  quantity: number,
  actor: ActorContext,
): Promise<CartItem> {
  const { data } = await api.post<CartItem>(
    '/api/v1/actions/cart',
    { ste_id: steId, quantity },
    buildActorConfig(actor),
  )
  return data
}

export async function updateCartItem(
  steId: string,
  quantity: number,
  actor: ActorContext,
): Promise<CartItem> {
  const { data } = await api.patch<CartItem>(
    `/api/v1/actions/cart/${steId}`,
    { quantity },
    buildActorConfig(actor),
  )
  return data
}

export async function removeCartItem(steId: string, actor: ActorContext): Promise<void> {
  await api.delete(`/api/v1/actions/cart/${steId}`, buildActorConfig(actor))
}

export async function createSearchEvent(payload: {
  session_id: string
  event_type: SearchEventType
  ste_id?: string
  supplier_id?: string
  category_id?: string
  query_text?: string
  normalized_query?: string
  corrected_query?: string | null
  page_type?: string
  page_url?: string
  referrer?: string
  rank_position?: number
  results_page?: number
  payload?: Record<string, unknown>
  actor: ActorContext
}) {
  const { actor, ...requestPayload } = payload
  const { data } = await api.post('/api/v1/events', requestPayload, buildActorConfig(actor))
  return data
}

export async function createSearchEventsBatch(payload: {
  items: Array<{
    session_id: string
    event_type: SearchEventType
    ste_id?: string
    supplier_id?: string
    category_id?: string
    query_text?: string
    normalized_query?: string
    corrected_query?: string | null
    page_type?: string
    page_url?: string
    referrer?: string
    rank_position?: number
    results_page?: number
    payload?: Record<string, unknown>
  }>
  actor: ActorContext
}) {
  const { actor, items } = payload
  const { data } = await api.post(
    '/api/v1/events/batch',
    { items },
    buildActorConfig(actor),
  )
  return data
}

export async function createSearchImpressions(payload: {
  items: Array<{
    search_session_id: string
    ste_id: string
    supplier_id?: string
    category_id?: string
    rank_position: number
    results_page?: number
    visible?: boolean
  }>
  actor: ActorContext
}) {
  const { actor, items } = payload
  const { data } = await api.post(
    '/api/v1/events/impressions',
    { items },
    buildActorConfig(actor),
  )
  return data
}

export async function createPurchase(payload: {
  ste_id: string
  quantity: number
  price?: number
  session_id?: string
  contract_id?: string
  actor: ActorContext
}) {
  const { actor, ...requestPayload } = payload
  const { data } = await api.post(
    '/api/v1/actions/purchases',
    requestPayload,
    buildActorConfig(actor),
  )
  return data
}

export async function getTelemetryEvents(payload: {
  actor: ActorContext
  user_id?: string
  search_session_id?: string
  limit?: number
}): Promise<TelemetryEventList> {
  const { actor, ...params } = payload
  const { data } = await api.get<TelemetryEventList>(
    '/api/v1/debug/telemetry/events',
    {
      ...buildActorConfig(actor),
      params,
    },
  )
  return data
}

export async function getTelemetryImpressions(payload: {
  actor: ActorContext
  user_id?: string
  search_session_id?: string
  limit?: number
}): Promise<TelemetryImpressionList> {
  const { actor, ...params } = payload
  const { data } = await api.get<TelemetryImpressionList>(
    '/api/v1/debug/telemetry/impressions',
    {
      ...buildActorConfig(actor),
      params,
    },
  )
  return data
}

export async function getTelemetryHealth(payload: {
  actor: ActorContext
  user_id?: string
  search_session_id?: string
}): Promise<TelemetryHealth> {
  const { actor, ...params } = payload
  const { data } = await api.get<TelemetryHealth>(
    '/api/v1/debug/telemetry/health',
    {
      ...buildActorConfig(actor),
      params,
    },
  )
  return data
}

export async function getSearchStackStatus(payload: {
  actor: ActorContext
}): Promise<SearchStackStatus> {
  const { actor } = payload
  const { data } = await api.get<SearchStackStatus>(
    '/api/v1/debug/search-stack',
    buildActorConfig(actor),
  )
  return data
}
