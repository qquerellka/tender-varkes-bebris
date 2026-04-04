import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons'
import { Button, Empty, Input, InputNumber, Skeleton, Tag, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import styled from 'styled-components'
import {
  getTelemetryEvents,
  getTelemetryHealth,
  getTelemetryImpressions,
  type ActorContext,
  type TelemetryEventList,
  type TelemetryHealth,
  type TelemetryImpressionList,
} from '@shared/api/search'
import { clearStoredSession, readStoredSession } from '@shared/lib/portal-session'
import PortalShell from '@widgets/portal-shell/PortalShell'

const Main = styled.main`
  width: min(1440px, calc(100% - 32px));
  margin: 0 auto;
  padding: 30px 0 40px;
`

const Hero = styled.section`
  display: grid;
  gap: 18px;
  padding: 20px;
  border: 1px solid #d9e0e8;
  background: #fff;
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
`

const HeroTop = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
`

const FiltersRow = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(180px, 0.8fr) auto;
  gap: 12px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`

const SummaryGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;

  @media (max-width: 980px) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  @media (max-width: 620px) {
    grid-template-columns: 1fr;
  }
`

const SummaryCard = styled.div`
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
`

const SummaryValue = styled.span`
  color: #2a3f5e;
  font-size: 22px;
  font-weight: 800;
`

const SummaryLabel = styled.span`
  color: #7a889b;
  font-size: 12px;
`

const Grid = styled.section`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 18px;

  @media (max-width: 1100px) {
    grid-template-columns: 1fr;
  }
`

const SectionCard = styled.section`
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid #dee6ee;
  background: #fff;
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
`

const SectionHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
`

const SectionTitle = styled(Typography.Title)`
  && {
    margin: 0;
    color: #30415a;
    font-size: 18px;
    font-weight: 700;
  }
`

const Feed = styled.div`
  display: grid;
  gap: 12px;
`

const CountList = styled.div`
  display: grid;
  gap: 8px;
`

const EventCard = styled.article`
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
`

const Meta = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: #66788d;
  font-size: 12px;
`

const Payload = styled.pre`
  margin: 0;
  padding: 12px;
  overflow: auto;
  border: 1px solid #dde6ef;
  background: #fff;
  color: #33465e;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
`

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}

function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function TelemetryDebugPage() {
  const session = readStoredSession()
  const navigate = useNavigate()
  const userId = session?.user_id ?? ''
  const actor: ActorContext = { userId }
  const [searchSessionId, setSearchSessionId] = useState('')
  const [limit, setLimit] = useState(20)
  const [appliedSearchSessionId, setAppliedSearchSessionId] = useState('')
  const [appliedLimit, setAppliedLimit] = useState(20)
  const [refreshNonce, setRefreshNonce] = useState(0)

  const isEnabled = Boolean(session)

  const eventsQuery = useQuery<TelemetryEventList>({
    queryKey: ['debug-telemetry-events', userId, appliedSearchSessionId, appliedLimit, refreshNonce],
    queryFn: () =>
      getTelemetryEvents({
        actor,
        search_session_id: appliedSearchSessionId || undefined,
        limit: appliedLimit,
      }),
    enabled: isEnabled,
  })

  const impressionsQuery = useQuery<TelemetryImpressionList>({
    queryKey: ['debug-telemetry-impressions', userId, appliedSearchSessionId, appliedLimit, refreshNonce],
    queryFn: () =>
      getTelemetryImpressions({
        actor,
        search_session_id: appliedSearchSessionId || undefined,
        limit: appliedLimit,
      }),
    enabled: isEnabled,
  })

  const healthQuery = useQuery<TelemetryHealth>({
    queryKey: ['debug-telemetry-health', userId, appliedSearchSessionId, refreshNonce],
    queryFn: () =>
      getTelemetryHealth({
        actor,
        search_session_id: appliedSearchSessionId || undefined,
      }),
    enabled: isEnabled,
  })

  if (!session) {
    return <Navigate to="/" replace />
  }

  const handleLogout = () => {
    clearStoredSession()
    navigate('/', { replace: true })
  }

  return (
    <PortalShell session={session} activeNav="debug" onLogout={handleLogout}>
      <Main>
        <Hero>
          <HeroTop>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
              Назад в кабинет
            </Button>
            <Tag color="purple">Internal Debug · Telemetry</Tag>
          </HeroTop>

          <div style={{ display: 'grid', gap: 8 }}>
            <Typography.Title level={2} style={{ margin: 0, color: '#2b3950' }}>
              Живая telemetry без SQL
            </Typography.Title>
            <Typography.Paragraph style={{ margin: 0, color: '#607085', fontSize: 16 }}>
              Экран читает debug API и показывает последние пользовательские события и
              impressions для текущего demo-пользователя. Можно сузить выдачу по
              `search_session_id`.
            </Typography.Paragraph>
          </div>

          <FiltersRow>
            <Input
              size="large"
              placeholder="search_session_id"
              value={searchSessionId}
              onChange={(event) => setSearchSessionId(event.target.value)}
            />
            <InputNumber
              size="large"
              min={1}
              max={200}
              style={{ width: '100%' }}
              value={limit}
              onChange={(value) => setLimit(Number(value) || 20)}
            />
            <Button
              type="primary"
              icon={<ReloadOutlined />}
              onClick={() => {
                setAppliedSearchSessionId(searchSessionId.trim())
                setAppliedLimit(limit)
                setRefreshNonce((value) => value + 1)
              }}
            >
              Обновить
            </Button>
          </FiltersRow>

          <SummaryGrid>
            <SummaryCard>
              <SummaryValue>{session.user_id}</SummaryValue>
              <SummaryLabel>Текущий demo-user</SummaryLabel>
            </SummaryCard>
            <SummaryCard>
              <SummaryValue>{healthQuery.data?.events_count ?? eventsQuery.data?.total ?? 0}</SummaryValue>
              <SummaryLabel>Событий в выборке</SummaryLabel>
            </SummaryCard>
            <SummaryCard>
              <SummaryValue>{healthQuery.data?.impressions_count ?? impressionsQuery.data?.total ?? 0}</SummaryValue>
              <SummaryLabel>Impressions в выборке</SummaryLabel>
            </SummaryCard>
            <SummaryCard>
              <SummaryValue>{appliedSearchSessionId || 'all'}</SummaryValue>
              <SummaryLabel>Фильтр по session</SummaryLabel>
            </SummaryCard>
          </SummaryGrid>
        </Hero>

        <Grid>
          <SectionCard>
            <SectionHeader>
              <SectionTitle level={3}>Telemetry Health</SectionTitle>
              <Tag color="processing">
                CTR {(((healthQuery.data?.click_through_rate ?? 0) * 100)).toFixed(1)}%
              </Tag>
            </SectionHeader>

            {healthQuery.isLoading ? (
              <Skeleton active paragraph={{ rows: 6 }} />
            ) : healthQuery.data ? (
              <>
                <SummaryGrid>
                  <SummaryCard>
                    <SummaryValue>{healthQuery.data.search_sessions_count}</SummaryValue>
                    <SummaryLabel>Search sessions</SummaryLabel>
                  </SummaryCard>
                  <SummaryCard>
                    <SummaryValue>{healthQuery.data.result_clicked_count}</SummaryValue>
                    <SummaryLabel>Result clicked</SummaryLabel>
                  </SummaryCard>
                  <SummaryCard>
                    <SummaryValue>{healthQuery.data.result_opened_count}</SummaryValue>
                    <SummaryLabel>Result opened</SummaryLabel>
                  </SummaryCard>
                  <SummaryCard>
                    <SummaryValue>{healthQuery.data.purchase_completed_count}</SummaryValue>
                    <SummaryLabel>Purchase completed</SummaryLabel>
                  </SummaryCard>
                </SummaryGrid>

                <Meta>
                  <span>
                    sessions with impressions: {healthQuery.data.search_sessions_with_impressions_count}
                  </span>
                  <span>
                    sessions without impressions: {healthQuery.data.search_sessions_without_impressions_count}
                  </span>
                  <span>
                    open/click: {((healthQuery.data.open_after_click_rate ?? 0) * 100).toFixed(1)}%
                  </span>
                  <span>
                    purchase/intent: {((healthQuery.data.purchase_after_intent_rate ?? 0) * 100).toFixed(1)}%
                  </span>
                </Meta>

                <CountList>
                  {healthQuery.data.event_counts.slice(0, 12).map((item) => (
                    <EventCard key={item.key}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                        <Tag color="blue">{item.key}</Tag>
                        <Typography.Text strong>{item.count}</Typography.Text>
                      </div>
                    </EventCard>
                  ))}
                </CountList>
              </>
            ) : (
              <Empty description="Сводка telemetry пока недоступна." />
            )}
          </SectionCard>

          <SectionCard>
            <SectionHeader>
              <SectionTitle level={3}>Events</SectionTitle>
              <Tag color="processing">limit {appliedLimit}</Tag>
            </SectionHeader>

            {eventsQuery.isLoading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : eventsQuery.data?.items.length ? (
              <Feed>
                {eventsQuery.data.items.map((item) => (
                  <EventCard key={item.id}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      <Tag color="blue">{item.event_type}</Tag>
                      {item.page_type ? <Tag>{item.page_type}</Tag> : null}
                      {item.ste_id ? <Tag color="gold">СТЕ {item.ste_id}</Tag> : null}
                    </div>
                    <Meta>
                      <span>{formatDateTime(item.created_at)}</span>
                      <span>session: {item.session_id}</span>
                      {typeof item.rank_position === 'number' ? (
                        <span>rank: {item.rank_position}</span>
                      ) : null}
                      {typeof item.results_page === 'number' ? (
                        <span>page: {item.results_page}</span>
                      ) : null}
                    </Meta>
                    {(item.query_text || item.normalized_query || item.corrected_query) ? (
                      <Meta>
                        {item.query_text ? <span>query: {item.query_text}</span> : null}
                        {item.normalized_query ? (
                          <span>normalized: {item.normalized_query}</span>
                        ) : null}
                        {item.corrected_query ? (
                          <span>corrected: {item.corrected_query}</span>
                        ) : null}
                      </Meta>
                    ) : null}
                    <Payload>{prettyJson(item.payload)}</Payload>
                  </EventCard>
                ))}
              </Feed>
            ) : (
              <Empty description="События не найдены для текущего фильтра." />
            )}
          </SectionCard>

          <SectionCard>
            <SectionHeader>
              <SectionTitle level={3}>Impressions</SectionTitle>
              <Tag color="processing">limit {appliedLimit}</Tag>
            </SectionHeader>

            {impressionsQuery.isLoading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : impressionsQuery.data?.items.length ? (
              <Feed>
                {impressionsQuery.data.items.map((item) => (
                  <EventCard key={item.id}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      <Tag color="purple">search_impression</Tag>
                      <Tag>СТЕ {item.ste_id}</Tag>
                      <Tag color={item.visible ? 'green' : 'default'}>
                        {item.visible ? 'visible' : 'hidden'}
                      </Tag>
                    </div>
                    <Meta>
                      <span>{formatDateTime(item.rendered_at)}</span>
                      <span>session: {item.search_session_id}</span>
                      <span>rank: {item.rank_position}</span>
                      <span>page: {item.results_page}</span>
                    </Meta>
                    <Payload>{prettyJson(item)}</Payload>
                  </EventCard>
                ))}
              </Feed>
            ) : (
              <Empty description="Impressions не найдены для текущего фильтра." />
            )}
          </SectionCard>
        </Grid>
      </Main>
    </PortalShell>
  )
}

export default TelemetryDebugPage
