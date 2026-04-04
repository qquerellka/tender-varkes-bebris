import { Empty, Skeleton, Spin, Typography } from 'antd'
import styled from 'styled-components'
import type { SearchHistoryItem, SearchSuggestion } from '@shared/api/search'
import { demoScenarios } from '@entities/search/model/types'

const Hero = styled.section`
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 430px);
  gap: 28px;
  align-items: center;
  min-height: 360px;
  padding: 28px 0 40px;

  @media (max-width: 992px) {
    grid-template-columns: 1fr;
    min-height: auto;
    padding-top: 12px;
  }
`

const HeroStack = styled.div`
  display: grid;
  gap: 22px;
`

const Eyebrow = styled(Typography.Text)`
  color: #6b7785;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
`

const HeroTitle = styled(Typography.Title)`
  && {
    margin-top: 10px;
    margin-bottom: 12px;
    color: #263445;
    font-size: clamp(38px, 5vw, 64px);
    line-height: 0.98;
  }
`

const Lead = styled(Typography.Paragraph)`
  && {
    max-width: 640px;
    margin-bottom: 0;
    color: #647182;
    font-size: 20px;
  }
`

const LoaderCard = styled.div`
  padding: 24px;
  border: 1px solid #dce2e8;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.76);
  box-shadow: 0 20px 44px rgba(114, 129, 153, 0.14);
`

const CapabilityGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;

  @media (max-width: 720px) {
    grid-template-columns: 1fr;
  }
`

const CapabilityCard = styled.div`
  padding: 14px 16px;
  border: 1px solid #dbe3ed;
  background: rgba(255, 255, 255, 0.92);
`

const CapabilityValue = styled.div`
  color: #173b69;
  font-size: 18px;
  font-weight: 700;
`

const CapabilityLabel = styled.div`
  margin-top: 6px;
  color: #627082;
  font-size: 13px;
  line-height: 1.4;
`

const SuggestionsRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
`

const SuggestionChip = styled.button`
  padding: 9px 12px;
  border: 1px solid #d5dde7;
  border-radius: 999px;
  color: #2b456f;
  font: inherit;
  background: rgba(255, 255, 255, 0.88);
  cursor: pointer;

  &:hover {
    background: #f4f8ff;
  }
`

const Section = styled.section`
  margin-top: 28px;
`

const SectionTitle = styled(Typography.Title)`
  && {
    margin: 0 0 14px;
    color: #22364f;
    font-size: 16px;
    font-weight: 700;
  }
`

const CardGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;

  @media (max-width: 720px) {
    grid-template-columns: 1fr;
  }
`

const ClickCard = styled.button`
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 14px 16px;
  border: 1px solid #d5dde7;
  color: #263445;
  font: inherit;
  text-align: left;
  background: rgba(255, 255, 255, 0.92);
  cursor: pointer;

  &:hover {
    background: #f4f8ff;
  }
`

const CardTitle = styled.span`
  font-size: 14px;
  font-weight: 700;
`

const CardMeta = styled.span`
  color: #6a7787;
  font-size: 12px;
`

type SearchHeroProps = {
  history: SearchHistoryItem[]
  historyLoading?: boolean
  suggestions: SearchSuggestion[]
  onApplyHistory: (query: string) => void
  onApplySuggestion: (query: string) => void
  onApplyDemoScenario: (query: string) => void
}

export function SearchHero({
  history,
  historyLoading = false,
  suggestions,
  onApplyHistory,
  onApplySuggestion,
  onApplyDemoScenario,
}: SearchHeroProps) {
  const chips = [...history.map((item) => item.query), ...suggestions.map((item) => item.label)]
  const uniqueChips = Array.from(new Set(chips)).slice(0, 6)
  const recentHistory = history.slice(0, 4)

  return (
    <Hero>
      <HeroStack>
        <div>
          <Eyebrow>Умный поиск по каталогу СТЕ</Eyebrow>
          <HeroTitle level={1}>Демо выдачи для закупочного портала</HeroTitle>
          <Lead>
            Поиск уже подключен к backend: учитываются исправление опечаток,
            синонимы из БД, история запросов, гибридный retrieval и персонализация
            по активному demo-профилю.
          </Lead>
        </div>

        <CapabilityGrid>
          <CapabilityCard>
            <CapabilityValue>Spellcheck</CapabilityValue>
            <CapabilityLabel>
              Опечатки исправляются до ранжирования и отражаются в metadata выдачи.
            </CapabilityLabel>
          </CapabilityCard>
          <CapabilityCard>
            <CapabilityValue>Synonyms</CapabilityValue>
            <CapabilityLabel>
              Синонимы и доменные формулировки читаются из PostgreSQL, а не из frontend.
            </CapabilityLabel>
          </CapabilityCard>
          <CapabilityCard>
            <CapabilityValue>Personalization</CapabilityValue>
            <CapabilityLabel>
              Результаты бустятся историей закупок, recent STE и популярностью в организации.
            </CapabilityLabel>
          </CapabilityCard>
        </CapabilityGrid>

        {uniqueChips.length ? (
          <SuggestionsRow>
            {uniqueChips.map((query) => (
              <SuggestionChip
                key={query}
                type="button"
                onClick={() => {
                  const isHistory = history.some((item) => item.query === query)
                  if (isHistory) {
                    onApplyHistory(query)
                    return
                  }
                  onApplySuggestion(query)
                }}
              >
                {query}
              </SuggestionChip>
            ))}
          </SuggestionsRow>
        ) : null}

        <Section>
          <SectionTitle level={3}>Готовые demo-сценарии</SectionTitle>
          <CardGrid>
            {demoScenarios.map((scenario) => (
              <ClickCard
                key={scenario.query}
                type="button"
                onClick={() => onApplyDemoScenario(scenario.query)}
              >
                <CardTitle>{scenario.label}</CardTitle>
                <CardMeta>{scenario.query}</CardMeta>
              </ClickCard>
            ))}
          </CardGrid>
        </Section>

        {recentHistory.length ? (
          <Section>
            <SectionTitle level={3}>Недавние запросы</SectionTitle>
            <CardGrid>
              {recentHistory.map((item) => (
                <ClickCard key={item.id} type="button" onClick={() => onApplyHistory(item.query)}>
                  <CardTitle>{item.query}</CardTitle>
                  <CardMeta>Нормализовано: {item.normalized_query}</CardMeta>
                </ClickCard>
              ))}
            </CardGrid>
          </Section>
        ) : historyLoading ? (
          <Section>
            <SectionTitle level={3}>Недавние запросы</SectionTitle>
            <Skeleton active paragraph={{ rows: 3 }} />
          </Section>
        ) : (
          <Section>
            <SectionTitle level={3}>Недавние запросы</SectionTitle>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="История появится после первых поисков этого профиля"
            />
          </Section>
        )}
      </HeroStack>

      <LoaderCard>
        <Spin size="large" />
        <Typography.Paragraph style={{ marginTop: 16, marginBottom: 8 }}>
          Страница ждет первый запрос и подготовит выдачу, детали позиции и похожие СТЕ.
        </Typography.Paragraph>
        <Skeleton active title={{ width: '70%' }} paragraph={{ rows: 4 }} />
      </LoaderCard>
    </Hero>
  )
}
