import { Tag, Typography } from 'antd'
import styled from 'styled-components'
import type { SearchItem } from '@shared/api/search'
import { formatSearchReason } from '@entities/search/lib/formatters'

const Card = styled.button<{ $selected: boolean }>`
  padding: 18px 20px;
  text-align: left;
  border: 0;
  border-top: 1px solid rgba(127, 135, 146, 0.18);
  background: ${({ $selected }) => ($selected ? '#f4f8ff' : 'transparent')};
  cursor: pointer;

  &:first-child {
    border-top: 0;
  }

  &:hover {
    background: #f7faff;
  }
`

const Title = styled(Typography.Title)`
  && {
    margin: 0 0 8px;
    color: #20406d;
    font-size: 18px;
    font-weight: 600;
  }
`

const Description = styled(Typography.Paragraph)`
  && {
    margin-bottom: 14px;
    color: #5a6777;
    font-size: 14px;
  }
`

const Meta = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`

const ResultTag = styled(Tag)`
  margin-inline-end: 0;
`

type SearchResultCardProps = {
  item: SearchItem
  selected: boolean
  onClick: () => void
}

export function SearchResultCard({ item, selected, onClick }: SearchResultCardProps) {
  return (
    <Card type="button" $selected={selected} onClick={onClick}>
      <Title level={3}>{item.title}</Title>
      <Description>{item.description}</Description>
      <Meta>
        <Tag color="geekblue">{item.category}</Tag>
        <Tag>{item.supplier}</Tag>
        <Tag color="green">score {item.score.toFixed(2)}</Tag>
        {item.reasons.map((reason) => (
          <ResultTag color="blue" key={reason}>
            {formatSearchReason(reason)}
          </ResultTag>
        ))}
      </Meta>
    </Card>
  )
}
