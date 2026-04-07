import { Empty, Pagination, Skeleton, Typography } from 'antd'
import styled from 'styled-components'
import { SearchResultCard } from '@entities/search/ui/search-result-card'
import type { SearchItem, SearchResponse } from '@shared/api/search'

const Panel = styled.section`
  overflow: hidden;
  border: 1px solid rgba(127, 135, 146, 0.2);
  background: rgba(255, 255, 255, 0.9);
`

const PanelHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 56px;
  padding: 0 18px;
  background: #ecf1f9;
  border-bottom: 1px solid rgba(127, 135, 146, 0.2);
`

const PanelTitle = styled(Typography.Title)`
  && {
    margin: 0;
    color: #1a1a1a;
    font-size: 20px;
    font-weight: 600;
  }
`

const PanelMeta = styled(Typography.Text)`
  color: #5f6d7e;
  font-size: 13px;
`

const PanelHint = styled(Typography.Text)`
  display: block;
  padding: 12px 18px;
  color: #657385;
  font-size: 12px;
  background: rgba(244, 248, 252, 0.8);
  border-bottom: 1px solid rgba(127, 135, 146, 0.12);
`

const ResultList = styled.div`
  display: grid;
`

const PaginationWrap = styled.div`
  display: flex;
  justify-content: flex-end;
  padding: 16px 18px 18px;
  border-top: 1px solid rgba(127, 135, 146, 0.12);
  background: rgba(248, 251, 253, 0.9);
`

type SearchResultsPanelProps = {
  state:
    | { kind: 'loading'; query: string }
    | { kind: 'results'; response: SearchResponse }
  currentPage: number
  pageSize: number
  selectedResultId: string | null
  total: number
  onPageChange: (page: number) => void
  onSelect: (item: SearchItem, position: number) => void
}

export function SearchResultsPanel({
  currentPage,
  pageSize,
  state,
  selectedResultId,
  total,
  onPageChange,
  onSelect,
}: SearchResultsPanelProps) {
  if (state.kind === 'loading') {
    return (
      <Panel>
        <PanelHeader>
          <PanelTitle level={2}>Результаты поиска</PanelTitle>
          <PanelMeta>Ищем: {state.query}</PanelMeta>
        </PanelHeader>
        <div style={{ padding: 20 }}>
          <Skeleton active paragraph={{ rows: 6 }} />
        </div>
      </Panel>
    )
  }

  return (
    <Panel>
      <PanelHeader>
        <PanelTitle level={2}>Результаты поиска</PanelTitle>
        <PanelMeta>
          Найдено: {state.response.items.length}
          {state.response.meta.corrected_query
            ? ` · исправлено: ${state.response.meta.corrected_query}`
            : ''}
        </PanelMeta>
      </PanelHeader>
      <PanelHint>
        Выдача обновляется автоматически при вводе, смене пользователя и переключении strict match.
      </PanelHint>

      {state.response.items.length ? (
        <>
          <ResultList>
            {state.response.items.map((item, index) => (
              <SearchResultCard
                key={item.id}
                item={item}
                selected={selectedResultId === item.id}
                onClick={() => onSelect(item, (currentPage - 1) * pageSize + index + 1)}
              />
            ))}
          </ResultList>
          {total > pageSize ? (
            <PaginationWrap>
              <Pagination
                current={currentPage}
                pageSize={pageSize}
                total={total}
                showSizeChanger={false}
                onChange={onPageChange}
              />
            </PaginationWrap>
          ) : null}
        </>
      ) : (
        <div style={{ padding: 28 }}>
          <Empty description="По этому запросу пока нет результатов. Попробуйте отключить strict match или выбрать другой demo-профиль." />
        </div>
      )}
    </Panel>
  )
}
