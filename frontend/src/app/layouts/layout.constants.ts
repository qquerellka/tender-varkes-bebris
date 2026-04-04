export const searchScopeOptions = [
  { value: 'catalog', label: 'Каталог продукции' },
  { value: 'procurements', label: 'Закупки' },
  { value: 'contracts', label: 'Контракты' },
  { value: 'organizations', label: 'Организации' },
  { value: 'all', label: 'Все категории' },
]

export type SearchScope = (typeof searchScopeOptions)[number]['value']
