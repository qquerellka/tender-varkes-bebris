import type { SearchScope } from '@app/layouts/layout.constants'
import type { SearchResponse } from '@shared/api/search'

export const demoScenarios = [
  { label: 'Автобус для детей', query: 'автобус для детей' },
  { label: 'Серверное оборудование', query: 'серверноое оборудование' },
  { label: 'Клининг офиса', query: 'клининг' },
  { label: 'Офисная бумага', query: 'бумга' },
  { label: 'Ноутбуки и рабочие места', query: 'ноутубк' },
] as const

export const supportedScopes: SearchScope[] = ['catalog', 'all']

export type SuggestionSource = 'history' | 'suggestion' | 'demo'

export type SearchState =
  | { kind: 'idle' }
  | { kind: 'unsupported'; scope: SearchScope }
  | { kind: 'loading'; query: string }
  | { kind: 'results'; response: SearchResponse }
  | { kind: 'error'; message: string }
