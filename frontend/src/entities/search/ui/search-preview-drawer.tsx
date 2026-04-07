import { Drawer, Skeleton, Tag, Typography } from 'antd'
import styled from 'styled-components'
import type { RelatedSearchItem, SearchItem, SearchResponse } from '@shared/api/search'
import { formatRelatedReason, formatSearchReason } from '@entities/search/lib/formatters'

const Section = styled.div`
  display: grid;
  gap: 20px;
`

const QuerySummary = styled.div`
  display: grid;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid rgba(127, 135, 146, 0.18);
  background: #f8fbff;
`

const SummaryGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
`

const SummaryItem = styled.div`
  display: grid;
  gap: 4px;
`

const SummaryLabel = styled.span`
  color: #677385;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
`

const SummaryValue = styled.span`
  color: #203244;
  font-size: 14px;
  line-height: 1.4;
`

const MetaRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`

const RelatedList = styled.div`
  display: grid;
  gap: 12px;
`

const RelatedCard = styled.div`
  padding: 14px 16px;
  border: 1px solid rgba(127, 135, 146, 0.18);
  background: #fafcff;
`

const RelatedTitle = styled(Typography.Title)`
  && {
    margin: 0 0 6px;
    color: #20406d;
    font-size: 16px;
    font-weight: 600;
  }
`

type SearchPreviewDrawerProps = {
  open: boolean
  item: SearchItem | null
  response: SearchResponse | null
  relatedItems: RelatedSearchItem[]
  relatedLoading: boolean
  onClose: () => void
}

export function SearchPreviewDrawer({
  open,
  item,
  response,
  relatedItems,
  relatedLoading,
  onClose,
}: SearchPreviewDrawerProps) {
  return (
    <Drawer
      title={item ? 'Карточка позиции' : 'Результат'}
      placement="right"
      width={520}
      open={open}
      onClose={onClose}
      destroyOnClose={false}
    >
      {item && response ? (
        <Section>
          <QuerySummary>
            <SummaryGrid>
              <SummaryItem>
                <SummaryLabel>Исходный запрос</SummaryLabel>
                <SummaryValue>{response.meta.query}</SummaryValue>
              </SummaryItem>
              <SummaryItem>
                <SummaryLabel>Нормализованный</SummaryLabel>
                <SummaryValue>{response.meta.normalized_query}</SummaryValue>
              </SummaryItem>
              <SummaryItem>
                <SummaryLabel>Исправление</SummaryLabel>
                <SummaryValue>{response.meta.corrected_query ?? 'Не применялось'}</SummaryValue>
              </SummaryItem>
              <SummaryItem>
                <SummaryLabel>Сессия</SummaryLabel>
                <SummaryValue>{response.meta.session_id}</SummaryValue>
              </SummaryItem>
            </SummaryGrid>

            <div>
              <SummaryLabel>Примененные синонимы</SummaryLabel>
              <MetaRow style={{ marginTop: 8 }}>
                {response.meta.applied_synonyms.length ? (
                  response.meta.applied_synonyms.map((synonym) => (
                    <Tag key={synonym} color="processing">
                      {synonym}
                    </Tag>
                  ))
                ) : (
                  <Tag>Нет</Tag>
                )}
              </MetaRow>
            </div>
          </QuerySummary>

          <div>
            <Typography.Title level={3} style={{ marginTop: 0, marginBottom: 8 }}>
              {item.title}
            </Typography.Title>
            <Typography.Paragraph style={{ color: '#5a6777' }}>
              {item.description}
            </Typography.Paragraph>
            <MetaRow>
              <Tag color="geekblue">{item.category}</Tag>
              <Tag>{item.supplier}</Tag>
              <Tag color="green">score {item.score.toFixed(2)}</Tag>
            </MetaRow>
            <MetaRow style={{ marginTop: 10 }}>
              {item.reasons.map((reason) => (
                <Tag color="blue" key={reason}>
                  {formatSearchReason(reason)}
                </Tag>
              ))}
            </MetaRow>
          </div>

          <div>
            <Typography.Title level={4} style={{ marginTop: 0 }}>
              Похожие позиции
            </Typography.Title>

            {relatedLoading ? (
              <Skeleton active paragraph={{ rows: 4 }} />
            ) : (
              <RelatedList>
                {relatedItems.length ? (
                  relatedItems.map((relatedItem) => (
                    <RelatedCard key={relatedItem.id}>
                      <RelatedTitle level={5}>{relatedItem.title}</RelatedTitle>
                      <Typography.Paragraph style={{ marginBottom: 10, color: '#5a6777' }}>
                        {relatedItem.description}
                      </Typography.Paragraph>
                      <MetaRow>
                        <Tag color="geekblue">{relatedItem.category_name}</Tag>
                        <Tag>{relatedItem.supplier_name}</Tag>
                        <Tag color="green">score {relatedItem.score.toFixed(2)}</Tag>
                      </MetaRow>
                      <MetaRow style={{ marginTop: 10 }}>
                        {relatedItem.reasons.map((reason) => (
                          <Tag key={reason}>{formatRelatedReason(reason)}</Tag>
                        ))}
                      </MetaRow>
                    </RelatedCard>
                  ))
                ) : (
                  <Typography.Text type="secondary">
                    Похожие позиции пока не найдены.
                  </Typography.Text>
                )}
              </RelatedList>
            )}
          </div>
        </Section>
      ) : null}
    </Drawer>
  )
}
