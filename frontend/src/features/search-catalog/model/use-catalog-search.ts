import {
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useMemo,
  useRef,
  useState,
  useTransition,
} from 'react'
import { useQuery } from '@tanstack/react-query'
import type { SearchScope } from '@app/layouts/layout.constants'
import { buildAutocompleteOptions } from '@entities/search/lib/formatters'
import { supportedScopes, type SearchState, type SuggestionSource } from '@entities/search/model/types'
import { demoUsers } from './demo-users'
import {
  createSearchEvent,
  getCategories,
  getRelatedItems,
  getPurchaseHistory,
  getSearchProfile,
  getSearchHistory,
  getSearchSuggestions,
  getSuppliers,
  type CatalogCategory,
  type CatalogSupplier,
  type PurchaseHistoryItem,
  searchCatalog,
  type SearchItem,
  type SearchProfileResponse,
  type SearchResponse,
} from '@shared/api/search'
import { writeLastSearchSessionId } from '@shared/lib/portal-session'
import { useDebouncedValue } from '@shared/lib/use-debounced-value'

const STORAGE_KEYS = {
  activeUserId: 'catalog-demo-active-user-id',
  searchValue: 'catalog-demo-search-value',
  searchScope: 'catalog-demo-search-scope',
  strictMatch: 'catalog-demo-strict-match',
  categoryId: 'catalog-demo-category-id',
  supplierId: 'catalog-demo-supplier-id',
} as const

const RESULTS_PER_PAGE = 8
const SEARCH_SUGGESTIONS_DEBOUNCE_MS = 350

function readStoredValue(key: string): string | null {
  if (typeof window === 'undefined') {
    return null
  }

  return window.localStorage.getItem(key)
}

export function useCatalogSearch() {
  const [searchValue, setSearchValue] = useState(() => readStoredValue(STORAGE_KEYS.searchValue) ?? '')
  const [searchScope, setSearchScope] = useState<SearchScope>(() => {
    const storedScope = readStoredValue(STORAGE_KEYS.searchScope)
    return storedScope === 'catalog' || storedScope === 'all' ? storedScope : 'catalog'
  })
  const [strictMatch, setStrictMatch] = useState(
    () => readStoredValue(STORAGE_KEYS.strictMatch) === 'true',
  )
  const [selectedCategoryId, setSelectedCategoryId] = useState(
    () => readStoredValue(STORAGE_KEYS.categoryId) ?? undefined,
  )
  const [selectedSupplierId, setSelectedSupplierId] = useState(
    () => readStoredValue(STORAGE_KEYS.supplierId) ?? undefined,
  )
  const [searchState, setSearchState] = useState<SearchState>({ kind: 'idle' })
  const [selectedItem, setSelectedItem] = useState<SearchItem | null>(null)
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [resultsPage, setResultsPage] = useState(1)
  const [activeUserId, setActiveUserId] = useState(() => {
    const storedUserId = readStoredValue(STORAGE_KEYS.activeUserId)
    return demoUsers.some((user) => user.id === storedUserId) ? storedUserId! : (demoUsers[0]?.id ?? '')
  })
  const [contextNotice, setContextNotice] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()
  const deferredSearchValue = useDeferredValue(searchValue.trim())
  const debouncedSuggestionsValue = useDebouncedValue(
    deferredSearchValue,
    SEARCH_SUGGESTIONS_DEBOUNCE_MS,
  )
  const activeActor = useMemo(() => ({ userId: activeUserId }), [activeUserId])
  const activeUser = useMemo(
    () => demoUsers.find((user) => user.id === activeUserId) ?? demoUsers[0],
    [activeUserId],
  )
  const lastRunKeyRef = useRef<string | null>(null)
  const skipAutoSearchRef = useRef(false)

  const historyQuery = useQuery({
    queryKey: ['search-history', activeUserId],
    queryFn: () => getSearchHistory(activeActor),
  })

  const suggestionsQuery = useQuery({
    queryKey: ['search-suggestions', activeUserId, debouncedSuggestionsValue],
    queryFn: ({ signal }) => getSearchSuggestions(debouncedSuggestionsValue, activeActor, signal),
    enabled: debouncedSuggestionsValue.length > 2,
    retry: false,
  })

  const relatedQuery = useQuery({
    queryKey: ['related-items', selectedResultId],
    queryFn: () => getRelatedItems(selectedResultId!, 4),
    enabled: selectedResultId !== null && previewOpen,
  })

  const profileQuery = useQuery<SearchProfileResponse>({
    queryKey: ['search-profile', activeUserId],
    queryFn: () => getSearchProfile(activeActor),
  })

  const categoriesQuery = useQuery<CatalogCategory[]>({
    queryKey: ['catalog-categories'],
    queryFn: getCategories,
  })

  const suppliersQuery = useQuery<CatalogSupplier[]>({
    queryKey: ['catalog-suppliers'],
    queryFn: getSuppliers,
  })

  const purchaseHistoryQuery = useQuery<PurchaseHistoryItem[]>({
    queryKey: ['purchase-history', activeUserId],
    queryFn: () => getPurchaseHistory(activeActor),
  })

  const unsupportedScopeHint = useMemo(() => {
    if (supportedScopes.includes(searchScope)) {
      return null
    }

    return 'В демо сейчас подключен только поиск по каталогу СТЕ. Остальные разделы оставлены как будущие режимы.'
  }, [searchScope])

  const currentSessionId =
    searchState.kind === 'results' ? searchState.response.meta.session_id : undefined

  const suggestionsReady = searchValue.trim() === debouncedSuggestionsValue
  const suggestionItems = suggestionsReady ? suggestionsQuery.data?.items ?? [] : []

  const autocompleteOptions = buildAutocompleteOptions(suggestionItems)
  const suggestionsHint =
    suggestionsReady &&
    suggestionsQuery.data?.meta.correction_type !== 'none' &&
    suggestionsQuery.data?.meta.corrected_query
      ? `Подсказки для: ${suggestionsQuery.data.meta.effective_query}`
      : null

  const applySearchResponse = (response: SearchResponse) => {
    startTransition(() => {
      setSearchState({ kind: 'results', response })
      setResultsPage(1)
      setSelectedItem(null)
      setSelectedResultId(null)
      setPreviewOpen(false)
    })
  }

  const handleSearchRequest = async (
    query: string,
    actor = activeActor,
    eventMeta?: {
      type: 'suggestion_clicked'
      label: string
      source: SuggestionSource
    },
  ) => {
    const response = await searchCatalog({
      query,
      filters: {
        strict_match: strictMatch,
        category_id: selectedCategoryId,
        supplier_id: selectedSupplierId,
      },
      actor,
    })

    writeLastSearchSessionId(response.meta.session_id)
    applySearchResponse(response)

    if (eventMeta) {
      void createSearchEvent({
        session_id: response.meta.session_id,
        event_type: eventMeta.type,
        payload: {
          label: eventMeta.label,
          source: eventMeta.source,
        },
        actor,
      })
    }
  }

  const runSearch = async (
    query: string,
    eventSource?: SuggestionSource,
    actor = activeActor,
    options?: { strict?: boolean; scope?: SearchScope },
  ) => {
    const scope = options?.scope ?? searchScope
    const strict = options?.strict ?? strictMatch

    if (!supportedScopes.includes(scope)) {
      startTransition(() => {
        setSearchState({ kind: 'unsupported', scope })
      })
      return
    }

    lastRunKeyRef.current = `${actor.userId}::${scope}::${strict ? 'strict' : 'soft'}::${selectedCategoryId ?? 'all-categories'}::${selectedSupplierId ?? 'all-suppliers'}::${query.trim()}`
    startTransition(() => {
      setSearchState({ kind: 'loading', query })
    })

    try {
      await handleSearchRequest(
        query,
        actor,
        eventSource
          ? {
              type: 'suggestion_clicked',
              label: query,
              source: eventSource,
            }
          : undefined,
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Не удалось выполнить поиск'
      startTransition(() => {
        setSearchState({ kind: 'error', message })
        setResultsPage(1)
        setSelectedItem(null)
        setSelectedResultId(null)
        setPreviewOpen(false)
      })
    }
  }

  const handleSubmitSearch = async () => {
    const query = searchValue.trim()

    if (!query) {
      startTransition(() => {
        setSearchState({ kind: 'idle' })
        setResultsPage(1)
        setPreviewOpen(false)
      })
      return
    }

    await runSearch(query)
  }

  const applySuggestion = async (query: string, source: SuggestionSource) => {
    setSearchValue(query)
    await runSearch(query, source)
  }

  const handleSearchValueChange = (value: string) => {
    setSearchValue(value)

    if (value.trim()) {
      return
    }

    lastRunKeyRef.current = null
    setSelectedItem(null)
    setSelectedResultId(null)
    setPreviewOpen(false)
    setResultsPage(1)
    startTransition(() => {
      setSearchState({ kind: 'idle' })
    })
  }

  const selectResult = (item: SearchItem, position: number) => {
    setSelectedItem(item)
    setSelectedResultId(item.id)
    setPreviewOpen(true)

    if (!currentSessionId) {
      return
    }

    void createSearchEvent({
      session_id: currentSessionId,
      event_type: 'result_clicked',
      ste_id: item.id,
      payload: {
        position,
        score: item.score,
      },
      actor: activeActor,
    })
  }

  const handleActiveUserChange = (nextUserId: string) => {
    const nextUser = demoUsers.find((user) => user.id === nextUserId)
    setActiveUserId(nextUserId)
    setSelectedItem(null)
    setSelectedResultId(null)
    setPreviewOpen(false)
    setResultsPage(1)
    setContextNotice(nextUser ? `Контекст обновлен: ${nextUser.name} · ${nextUser.persona}` : null)
    skipAutoSearchRef.current = true

    if (!searchValue.trim()) {
      setSearchState({ kind: 'idle' })
      return
    }

    void runSearch(searchValue.trim(), undefined, { userId: nextUserId })
  }

  const clearDemoContext = () => {
    const controlUserId = demoUsers[0]?.id ?? ''

    setSearchValue('')
    setSearchScope('catalog')
    setStrictMatch(false)
    setSelectedItem(null)
    setSelectedResultId(null)
    setPreviewOpen(false)
    setResultsPage(1)
    setSelectedCategoryId(undefined)
    setSelectedSupplierId(undefined)
    setSearchState({ kind: 'idle' })
    setActiveUserId(controlUserId)
    setContextNotice('Контекст сброшен до baseline-режима')
    lastRunKeyRef.current = null
    skipAutoSearchRef.current = true
  }

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem(STORAGE_KEYS.searchValue, searchValue)
  }, [searchValue])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem(STORAGE_KEYS.searchScope, searchScope)
  }, [searchScope])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem(STORAGE_KEYS.strictMatch, String(strictMatch))
  }, [strictMatch])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    if (selectedCategoryId) {
      window.localStorage.setItem(STORAGE_KEYS.categoryId, selectedCategoryId)
      return
    }

    window.localStorage.removeItem(STORAGE_KEYS.categoryId)
  }, [selectedCategoryId])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    if (selectedSupplierId) {
      window.localStorage.setItem(STORAGE_KEYS.supplierId, selectedSupplierId)
      return
    }

    window.localStorage.removeItem(STORAGE_KEYS.supplierId)
  }, [selectedSupplierId])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem(STORAGE_KEYS.activeUserId, activeUserId)
  }, [activeUserId])

  useEffect(() => {
    if (!contextNotice) {
      return
    }

    const timer = window.setTimeout(() => setContextNotice(null), 2600)
    return () => window.clearTimeout(timer)
  }, [contextNotice])

  const triggerAutoSearch = useEffectEvent((query: string) => {
    void runSearch(query)
  })

  useEffect(() => {
    const query = searchValue.trim()

    if (!query) {
      return
    }

    if (query.length < 2 || !supportedScopes.includes(searchScope)) {
      return
    }

    const nextRunKey = `${activeUserId}::${searchScope}::${strictMatch ? 'strict' : 'soft'}::${selectedCategoryId ?? 'all-categories'}::${selectedSupplierId ?? 'all-suppliers'}::${query}`
    if (skipAutoSearchRef.current) {
      skipAutoSearchRef.current = false
      return
    }

    if (lastRunKeyRef.current === nextRunKey) {
      return
    }

    const timer = window.setTimeout(() => {
      triggerAutoSearch(query)
    }, 450)

    return () => window.clearTimeout(timer)
  }, [searchValue, activeUserId, searchScope, strictMatch, selectedCategoryId, selectedSupplierId])

  const setCategoryFilter = (categoryId?: string) => {
    setSelectedCategoryId(categoryId)
    setResultsPage(1)
    lastRunKeyRef.current = null
  }

  const setSupplierFilter = (supplierId?: string) => {
    setSelectedSupplierId(supplierId)
    setResultsPage(1)
    lastRunKeyRef.current = null
  }

  const clearSearchFilters = () => {
    setSelectedCategoryId(undefined)
    setSelectedSupplierId(undefined)
    setStrictMatch(false)
    setResultsPage(1)
    lastRunKeyRef.current = null
  }

  const paginatedSearchState = useMemo(() => {
    if (searchState.kind !== 'results') {
      return searchState
    }

    const startIndex = (resultsPage - 1) * RESULTS_PER_PAGE
    const endIndex = startIndex + RESULTS_PER_PAGE

    return {
      kind: 'results' as const,
      response: {
        ...searchState.response,
        items: searchState.response.items.slice(startIndex, endIndex),
      },
    }
  }, [resultsPage, searchState])

  return {
    activeUser,
    activeUserId,
    activeUserProfile: profileQuery.data ?? null,
    contextNotice,
    demoUsers,
    isControlUser: activeUserId === demoUsers[0]?.id,
    categories: categoriesQuery.data ?? [],
    categoriesLoading: categoriesQuery.isFetching,
    selectedCategoryId,
    profileLoading: profileQuery.isFetching,
    purchaseHistory: purchaseHistoryQuery.data ?? [],
    purchaseHistoryLoading: purchaseHistoryQuery.isFetching,
    selectedSupplierId,
    suppliers: suppliersQuery.data ?? [],
    suppliersLoading: suppliersQuery.isFetching,
    resultsPage,
    resultsPageSize: RESULTS_PER_PAGE,
    searchValue,
    searchScope,
    strictMatch,
    searchState: paginatedSearchState,
    searchTotal:
      searchState.kind === 'results' ? searchState.response.items.length : 0,
    selectedItem,
    selectedResultId,
    previewOpen,
    isSearching: searchState.kind === 'loading' || isPending,
    unsupportedScopeHint,
    autocompleteOptions,
    suggestionsHint,
    historyItems: historyQuery.data?.items ?? [],
    historyLoading: historyQuery.isFetching,
    idleSuggestions: suggestionsQuery.data?.items ?? [],
    relatedItems: relatedQuery.data ?? [],
    relatedLoading: relatedQuery.isFetching,
    clearDemoContext,
    clearSearchFilters,
    setResultsPage,
    setActiveUserId: handleActiveUserChange,
    setSelectedCategoryId: setCategoryFilter,
    setSearchValue: handleSearchValueChange,
    setSearchScope,
    setSelectedSupplierId: setSupplierFilter,
    setStrictMatch,
    setPreviewOpen,
    handleSubmitSearch,
    applySuggestion,
    selectResult,
  }
}
