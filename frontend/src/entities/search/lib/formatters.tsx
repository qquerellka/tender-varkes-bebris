import type { AutoCompleteProps } from 'antd'
import type { SearchSuggestion } from '@shared/api/search'

export function formatSearchReason(reason: string): string {
  const labels: Record<string, string> = {
    exact_title_match: 'Точное совпадение',
    prefix_title_match: 'Совпадение по началу названия',
    partial_title_match: 'Совпадение по названию',
    fuzzy_title_match: 'Учтена опечатка или близкая формулировка',
    description_match: 'Совпадение по описанию',
    token_match: 'Совпадение по ключевым словам',
    matches_purchase_history: 'Похоже на историю закупок',
    recent_interaction: 'Недавний интерес',
    popular_supplier: 'Часто выбираемый поставщик',
    popular_in_organization: 'Популярно в организации',
  }

  return labels[reason] ?? reason
}

export function formatRelatedReason(reason: string): string {
  const labels: Record<string, string> = {
    same_category: 'Та же категория',
    same_supplier: 'Тот же поставщик',
    title_overlap: 'Похожие формулировки',
    attribute_overlap: 'Совпадают атрибуты',
  }

  return labels[reason] ?? reason
}

export function formatSuggestionType(type: string): string {
  if (type === 'history') {
    return 'История'
  }

  if (type === 'category') {
    return 'Категория'
  }

  if (type === 'product') {
    return 'Товар'
  }

  return 'Подсказка'
}

export function formatSuggestionGroup(group: string): string {
  if (group === 'history') {
    return 'История'
  }

  if (group === 'categories') {
    return 'Категории'
  }

  if (group === 'products') {
    return 'Товары'
  }

  return 'Подсказки'
}

export function buildAutocompleteOptions(
  suggestions: SearchSuggestion[],
): NonNullable<AutoCompleteProps['options']> {
  const groupOrder = ['history', 'categories', 'products']
  const groupedSuggestions = groupOrder
    .map((group) => ({
      group,
      items: suggestions.filter((item) => item.group === group),
    }))
    .filter((entry) => entry.items.length > 0)

  return groupedSuggestions.map((entry) => ({
    label: (
      <div
        style={{
          color: '#647182',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}
      >
        {formatSuggestionGroup(entry.group)}
      </div>
    ),
    options: entry.items.map((item) => ({
      value: item.label,
      label: (
        <div style={{ display: 'grid', gap: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <span style={{ color: '#24364a', fontWeight: 600 }}>{item.label}</span>
            <span style={{ color: '#7a8797', fontSize: 12 }}>{formatSuggestionType(item.type)}</span>
          </div>
          {item.description ? (
            <span style={{ color: '#6f7d8e', fontSize: 12 }}>{item.description}</span>
          ) : null}
        </div>
      ),
    })),
  }))
}
