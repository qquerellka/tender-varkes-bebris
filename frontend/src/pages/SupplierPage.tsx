import {
  ArrowLeftOutlined,
  AppstoreOutlined,
  RiseOutlined,
  ShoppingCartOutlined,
} from '@ant-design/icons'
import { Button, Empty, Select, Skeleton, Tag, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import styled from 'styled-components'
import {
  activityFilterOptions,
  getActivityColor,
  getActivityFilterKey,
  type ActivityFilter,
} from '@entities/search/lib/activity'
import {
  getCatalogSummary,
  getSearchActivity,
  getSupplierInsights,
  type ActorContext,
  type CatalogSummary,
  type SearchActivityItem,
  type SupplierInsightsResponse,
} from '@shared/api/search'
import { clearStoredSession, readStoredSession } from '@shared/lib/portal-session'
import PortalShell from '@widgets/portal-shell/PortalShell'

type SupplierStarterScenario = {
  key: string
  title: string
  description: string
  query: string
  categoryId?: string
}

function buildSupplierStarterScenarios(persona: string | null | undefined): SupplierStarterScenario[] {
  const normalizedPersona = persona?.toLowerCase() ?? ''

  if (normalizedPersona.includes('ит')) {
    return [
      {
        key: 'supplier-it-server',
        title: 'Спрос на серверы',
        description: 'Откройте каталог сразу в серверном сегменте и посмотрите конкурентную выдачу.',
        query: 'сервер',
        categoryId: 'cat_it',
      },
      {
        key: 'supplier-it-network',
        title: 'Сетевое оборудование',
        description: 'Быстрый вход в смежный рынок коммутаторов и инфраструктурных позиций.',
        query: 'коммутатор',
        categoryId: 'cat_it',
      },
      {
        key: 'supplier-it-support',
        title: 'Сервисное сопровождение',
        description: 'Показывает услуги поддержки и эксплуатационный контекст по вашему сегменту.',
        query: 'техническая поддержка',
        categoryId: 'cat_service',
      },
    ]
  }

  if (normalizedPersona.includes('офис') || normalizedPersona.includes('канцел')) {
    return [
      {
        key: 'supplier-office-paper',
        title: 'Канцелярский спрос',
        description: 'Запускает выдачу по бумаге и расходникам для офисного снабжения.',
        query: 'бумага',
        categoryId: 'cat_office',
      },
      {
        key: 'supplier-office-furniture',
        title: 'Офисная мебель',
        description: 'Проверяет смежный сегмент мебели и оснащения рабочих мест.',
        query: 'офисная мебель',
        categoryId: 'cat_office',
      },
      {
        key: 'supplier-office-print',
        title: 'Печать и расходники',
        description: 'Открывает карточный сегмент картриджей и печатной инфраструктуры.',
        query: 'картридж',
        categoryId: 'cat_office',
      },
    ]
  }

  if (normalizedPersona.includes('услуг') || normalizedPersona.includes('сопровожд')) {
    return [
      {
        key: 'supplier-service-support',
        title: 'Сопровождение систем',
        description: 'Быстрый старт по сервисным закупкам и сопровождению.',
        query: 'сопровождение системы',
        categoryId: 'cat_service',
      },
      {
        key: 'supplier-service-cleaning',
        title: 'Клининг и facility',
        description: 'Показывает спрос на регулярные сервисные контракты.',
        query: 'клининг',
        categoryId: 'cat_service',
      },
      {
        key: 'supplier-service-office',
        title: 'Офисные услуги',
        description: 'Открывает смежный контур по поддержке и эксплуатации помещений.',
        query: 'обслуживание офиса',
        categoryId: 'cat_service',
      },
    ]
  }

  return [
    {
      key: 'supplier-transport-bus',
      title: 'Автобусные закупки',
      description: 'Стартовый сценарий по пассажирскому транспорту и типовой конкурентной выдаче.',
      query: 'автобус',
      categoryId: 'cat_transport',
    },
    {
      key: 'supplier-transport-children',
      title: 'Перевозка детей',
      description: 'Более узкий кейс для оценки спроса и смежных поставщиков.',
      query: 'перевозка детей',
      categoryId: 'cat_transport',
    },
    {
      key: 'supplier-transport-microbus',
      title: 'Микроавтобусы',
      description: 'Открывает соседний транспортный сегмент без ручного ввода фильтров.',
      query: 'микроавтобус',
      categoryId: 'cat_transport',
    },
  ]
}

function formatDateTime(value: string | null) {
  if (!value) {
    return '—'
  }

  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

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

const Actions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

const OnboardingStrip = styled.section`
  display: grid;
  gap: 16px;
  margin-top: 18px;
  padding: 20px;
  border: 1px solid #d9e0e8;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(249, 243, 236, 0.98) 100%);
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
`

const OnboardingHeader = styled.div`
  display: grid;
  gap: 6px;
`

const OnboardingTitle = styled.span`
  color: #2a3c56;
  font-size: 20px;
  font-weight: 800;
`

const OnboardingText = styled.span`
  color: #607085;
  font-size: 14px;
  line-height: 1.5;
`

const OnboardingGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;

  @media (max-width: 1100px) {
    grid-template-columns: 1fr;
  }
`

const OnboardingCard = styled.button`
  display: grid;
  gap: 8px;
  padding: 16px;
  border: 1px solid #e5ddd4;
  color: #273a53;
  font: inherit;
  text-align: left;
  background: #fff;
  cursor: pointer;

  &:hover {
    border-color: #c26d2d;
    background: #fffaf4;
  }
`

const OnboardingCardTitle = styled.span`
  color: #7c4a1a;
  font-size: 15px;
  font-weight: 800;
`

const OnboardingCardText = styled.span`
  color: #66778c;
  font-size: 13px;
  line-height: 1.45;
`

const OnboardingCardAction = styled.span`
  color: #c26d2d;
  font-size: 13px;
  font-weight: 800;
  text-transform: uppercase;
`

const Grid = styled.section`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 18px;

  @media (max-width: 980px) {
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

const SectionTitle = styled(Typography.Title)`
  && {
    margin: 0;
    color: #30415a;
    font-size: 18px;
    font-weight: 700;
  }
`

const InsightList = styled.div`
  display: grid;
  gap: 10px;
`

const InsightCard = styled.div`
  display: grid;
  gap: 5px;
  padding: 14px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
`

const InsightTitle = styled.span`
  color: #273a53;
  font-size: 14px;
  font-weight: 700;
`

const InsightMeta = styled.span`
  color: #6f7d8e;
  font-size: 12px;
  line-height: 1.45;
`

const HeroTags = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`

const EmptyState = styled.div`
  display: grid;
  gap: 12px;
  justify-items: start;
  padding: 8px 0 2px;
`

const EmptyText = styled.span`
  color: #67768a;
  font-size: 13px;
  line-height: 1.5;
`

const ActivityTimeline = styled.div`
  display: grid;
  gap: 12px;
`

const ActivityCard = styled.div`
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid #dde6ef;
  background: #fbfcfe;
`

const ActivityTop = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
`

const ActivityMeta = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
`

const ActivityTitle = styled.span`
  color: #2b3f5d;
  font-size: 14px;
  font-weight: 700;
`

const ActivityText = styled.span`
  color: #64748a;
  font-size: 13px;
  line-height: 1.5;
`

function SupplierPage() {
  const session = readStoredSession()
  const navigate = useNavigate()
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>('all')
  const userId = session?.user_id ?? ''
  const actor: ActorContext = { userId }
  const isEnabled = Boolean(session) && session?.role === 'supplier'
  const starterScenarios = buildSupplierStarterScenarios(session?.persona)
  const showOnboarding = session?.entry_mode === 'empty' || session?.entry_mode === 'context'

  const summaryQuery = useQuery<CatalogSummary>({
    queryKey: ['catalog-summary', userId],
    queryFn: () => getCatalogSummary(actor),
    enabled: isEnabled,
  })

  const supplierInsightsQuery = useQuery<SupplierInsightsResponse>({
    queryKey: ['supplier-insights', userId],
    queryFn: () => getSupplierInsights(actor),
    enabled: isEnabled,
  })

  const activityQuery = useQuery({
    queryKey: ['search-activity', userId],
    queryFn: () => getSearchActivity(actor, 10),
    enabled: isEnabled,
  })
  const filteredActivityItems = useMemo(
    () =>
      (activityQuery.data?.items ?? []).filter(
        (item) => activityFilter === 'all' || getActivityFilterKey(item.event_type) === activityFilter,
      ),
    [activityFilter, activityQuery.data?.items],
  )

  if (!session || session.role !== 'supplier') {
    return <Navigate to="/" replace />
  }

  const handleLogout = () => {
    clearStoredSession()
    navigate('/', { replace: true })
  }

  const openStarterScenario = (scenario: SupplierStarterScenario) => {
    navigate('/', {
      state: {
        starterScenario: {
          key: scenario.key,
          title: scenario.title,
          description: scenario.description,
          query: scenario.query,
          categoryId: scenario.categoryId,
        },
      },
    })
  }

  const primaryScenario = starterScenarios[0]
  const heroDescription =
    session.entry_mode === 'context'
      ? 'Организационный профиль уже подсказывает сегмент, но личная история действий еще не собрана. Запустите готовый сценарий, чтобы быстрее открыть спрос и конкуренцию.'
      : session.entry_mode === 'empty'
        ? 'Новый кабинет поставщика еще без сигналов и поисковой истории. Начните со стартового сценария и соберите первый рыночный срез.'
        : 'Отдельная рабочая зона для анализа конкурентов, категорий спроса и горячих возможностей по вашему сегменту.'

  return (
    <PortalShell session={session} activeNav="supplier" onLogout={handleLogout}>
      <Main>
        <Hero>
          <HeroTop>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
              Назад в кабинет
            </Button>
            <Tag color="orange" icon={<RiseOutlined />}>
              Supplier Dashboard
            </Tag>
          </HeroTop>

          <div style={{ display: 'grid', gap: 8 }}>
            <Typography.Title level={2} style={{ margin: 0, color: '#2b3950' }}>
              Экран поставщика
            </Typography.Title>
            <Typography.Paragraph style={{ margin: 0, color: '#607085', fontSize: 16 }}>
              {heroDescription}
            </Typography.Paragraph>
            <HeroTags>
              <Tag color="orange">{session.persona ?? 'Поставщик'}</Tag>
              <Tag color={session.entry_mode === 'history' ? 'blue' : 'gold'}>
                {session.entry_mode === 'history'
                  ? 'С историей'
                  : session.entry_mode === 'context'
                    ? 'С контекстом'
                    : 'Пустой кабинет'}
              </Tag>
            </HeroTags>
          </div>

          {supplierInsightsQuery.isLoading || summaryQuery.isLoading ? (
            <Skeleton active paragraph={{ rows: 6 }} />
          ) : supplierInsightsQuery.data && summaryQuery.data ? (
            <>
              <SummaryGrid>
                <SummaryCard>
                  <SummaryValue>
                    {supplierInsightsQuery.data.owned_catalog_items_count.toLocaleString('ru-RU')}
                  </SummaryValue>
                  <SummaryLabel>Позиции вашего ассортимента</SummaryLabel>
                </SummaryCard>
                <SummaryCard>
                  <SummaryValue>
                    {supplierInsightsQuery.data.owned_purchase_history_count.toLocaleString('ru-RU')}
                  </SummaryValue>
                  <SummaryLabel>Закупки по вашему сегменту</SummaryLabel>
                </SummaryCard>
                <SummaryCard>
                  <SummaryValue>
                    {supplierInsightsQuery.data.tracked_categories_count.toLocaleString('ru-RU')}
                  </SummaryValue>
                  <SummaryLabel>Категорий под наблюдением</SummaryLabel>
                </SummaryCard>
                <SummaryCard>
                  <SummaryValue>
                    {summaryQuery.data.suppliers_count.toLocaleString('ru-RU')}
                  </SummaryValue>
                  <SummaryLabel>Всего поставщиков в каталоге</SummaryLabel>
                </SummaryCard>
              </SummaryGrid>

              <Actions>
                <Button icon={<AppstoreOutlined />} onClick={() => navigate('/')}>
                  Перейти в каталог
                </Button>
                <Button icon={<ShoppingCartOutlined />} onClick={() => navigate('/cart')}>
                  Открыть черновик закупки
                </Button>
              </Actions>
            </>
          ) : (
            <Empty description="Supplier analytics пока недоступны." />
          )}
        </Hero>

        {showOnboarding ? (
          <OnboardingStrip>
            <OnboardingHeader>
              <OnboardingTitle>
                {session.entry_mode === 'context'
                  ? 'Организационный контекст уже есть, личный профиль еще пустой'
                  : 'Новый кабинет поставщика готов к первому сценарию'}
              </OnboardingTitle>
              <OnboardingText>
                {session.entry_mode === 'context'
                  ? 'Dashboard уже может показать часть рыночного контекста, но лучшие инсайты появятся после первых поисков и действий в каталоге.'
                  : 'У этого кабинета еще нет накопленной истории. Начните с готового сценария, чтобы быстро открыть свой сегмент и собрать первые сигналы.'}
              </OnboardingText>
              {session.entry_note ? <OnboardingText>{session.entry_note}</OnboardingText> : null}
            </OnboardingHeader>

            <OnboardingGrid>
              {starterScenarios.map((scenario) => (
                <OnboardingCard
                  key={scenario.key}
                  type="button"
                  onClick={() => openStarterScenario(scenario)}
                >
                  <Tag color="orange">Сценарий поставщика</Tag>
                  <OnboardingCardTitle>{scenario.title}</OnboardingCardTitle>
                  <OnboardingCardText>{scenario.description}</OnboardingCardText>
                  <OnboardingCardAction>Открыть в каталоге</OnboardingCardAction>
                </OnboardingCard>
              ))}
            </OnboardingGrid>
          </OnboardingStrip>
        ) : null}

        <SectionCard style={{ marginTop: 18 }}>
          <HeroTop>
            <SectionTitle level={3}>Последние действия</SectionTitle>
            <Select
              size="middle"
              value={activityFilter}
              style={{ minWidth: 180 }}
              onChange={(value) => setActivityFilter(value as ActivityFilter)}
              options={activityFilterOptions}
            />
          </HeroTop>
          {activityQuery.isLoading ? (
            <Skeleton active paragraph={{ rows: 5 }} />
          ) : filteredActivityItems.length ? (
            <ActivityTimeline>
              {filteredActivityItems.map((item: SearchActivityItem) => (
                <ActivityCard key={item.id}>
                  <ActivityTop>
                    <ActivityTitle>{item.title}</ActivityTitle>
                    <Typography.Text style={{ color: '#7a889b', fontSize: 12 }}>
                      {formatDateTime(item.created_at)}
                    </Typography.Text>
                  </ActivityTop>
                  <ActivityMeta>
                    <Tag color={getActivityColor(item.event_type)}>{item.event_type}</Tag>
                    {item.query ? <Tag>{item.query}</Tag> : null}
                    {item.ste_title ? <Tag color="geekblue">{item.ste_title}</Tag> : null}
                  </ActivityMeta>
                  <ActivityText>{item.description}</ActivityText>
                </ActivityCard>
              ))}
            </ActivityTimeline>
          ) : (activityQuery.data?.items ?? []).length ? (
            <EmptyState>
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="Для этого типа действий пока нет событий."
              />
              <EmptyText>
                Смените фильтр или продолжите работу в каталоге, чтобы собрать новые действия по
                нужному сценарию.
              </EmptyText>
              <Button onClick={() => setActivityFilter('all')}>Показать все действия</Button>
            </EmptyState>
          ) : (
            <EmptyState>
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="История действий пока пуста."
              />
              <EmptyText>
                После первых поисков, открытий карточек и действий с shortlist здесь появится
                живая лента поведения поставщика по текущему сегменту.
              </EmptyText>
              {session.entry_note ? <EmptyText>{session.entry_note}</EmptyText> : null}
              {primaryScenario ? (
                <Button type="primary" ghost onClick={() => openStarterScenario(primaryScenario)}>
                  Начать со сценария
                </Button>
              ) : null}
            </EmptyState>
          )}
        </SectionCard>

        {supplierInsightsQuery.isLoading ? (
          <SectionCard style={{ marginTop: 18 }}>
            <Skeleton active paragraph={{ rows: 10 }} />
          </SectionCard>
        ) : supplierInsightsQuery.data ? (
          <Grid>
            <SectionCard>
              <SectionTitle level={3}>Ваш контур</SectionTitle>
              <InsightList>
                {supplierInsightsQuery.data.matched_suppliers.length ? (
                  supplierInsightsQuery.data.matched_suppliers.map((item) => (
                    <InsightCard key={item.id}>
                      <InsightTitle>{item.name}</InsightTitle>
                      <InsightMeta>
                        Позиций: {item.catalog_items_count.toLocaleString('ru-RU')}
                      </InsightMeta>
                      <InsightMeta>
                        Закупок: {item.purchase_history_count.toLocaleString('ru-RU')}
                      </InsightMeta>
                      <InsightMeta>Overlap токенов: {item.token_overlap}</InsightMeta>
                    </InsightCard>
                  ))
                ) : (
                  <EmptyState>
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        showOnboarding
                          ? 'Совпавшие поставщики пока не найдены.'
                          : 'Совпавшие поставщики не найдены.'
                      }
                    />
                    <EmptyText>
                      {showOnboarding
                        ? 'Откройте стартовый сценарий и посмотрите, кто уже присутствует в вашем сегменте.'
                        : 'Попробуйте открыть каталог по смежной категории и проверить конкуренцию вручную.'}
                    </EmptyText>
                    {primaryScenario ? (
                      <Button onClick={() => openStarterScenario(primaryScenario)}>
                        Открыть первый сценарий
                      </Button>
                    ) : null}
                  </EmptyState>
                )}
              </InsightList>
            </SectionCard>

            <SectionCard>
              <SectionTitle level={3}>Спрос по категориям</SectionTitle>
              <InsightList>
                {supplierInsightsQuery.data.top_demand_categories.length ? (
                  supplierInsightsQuery.data.top_demand_categories.map((item) => (
                    <InsightCard key={item.id}>
                      <InsightTitle>{item.name}</InsightTitle>
                      <InsightMeta>
                        Позиций в категории: {item.catalog_items_count.toLocaleString('ru-RU')}
                      </InsightMeta>
                      <InsightMeta>
                        Закупок по истории: {item.purchase_count.toLocaleString('ru-RU')}
                      </InsightMeta>
                    </InsightCard>
                  ))
                ) : (
                  <EmptyState>
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        showOnboarding
                          ? 'Спросовые категории еще не определены.'
                          : 'Спросовые категории пока не определены.'
                      }
                    />
                    <EmptyText>
                      {showOnboarding
                        ? 'После первых поисков dashboard сможет показать, где в вашем сегменте есть устойчивый спрос.'
                        : 'Добавьте больше поисковых сигналов через каталог, чтобы расширить категорийный срез.'}
                    </EmptyText>
                    {primaryScenario ? (
                      <Button type="primary" ghost onClick={() => openStarterScenario(primaryScenario)}>
                        Посмотреть спрос в каталоге
                      </Button>
                    ) : null}
                  </EmptyState>
                )}
              </InsightList>
            </SectionCard>

            <SectionCard>
              <SectionTitle level={3}>Топ конкурентов</SectionTitle>
              <InsightList>
                {supplierInsightsQuery.data.top_competitors.length ? (
                  supplierInsightsQuery.data.top_competitors.map((item) => (
                    <InsightCard key={item.id}>
                      <InsightTitle>{item.name}</InsightTitle>
                      <InsightMeta>
                        Позиций в каталоге: {item.catalog_items_count.toLocaleString('ru-RU')}
                      </InsightMeta>
                      <InsightMeta>
                        Закупок в смежных категориях: {item.purchase_history_count.toLocaleString('ru-RU')}
                      </InsightMeta>
                    </InsightCard>
                  ))
                ) : (
                  <EmptyState>
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        showOnboarding ? 'Конкуренты пока не определены.' : 'Конкуренты пока не найдены.'
                      }
                    />
                    <EmptyText>
                      {showOnboarding
                        ? 'Готовый сценарий быстро покажет смежных поставщиков и поможет собрать конкурентный контур.'
                        : 'Переключитесь в каталог и проверьте смежные позиции, чтобы обновить конкурентную картину.'}
                    </EmptyText>
                    {primaryScenario ? (
                      <Button onClick={() => openStarterScenario(primaryScenario)}>
                        Открыть конкурентный сценарий
                      </Button>
                    ) : null}
                  </EmptyState>
                )}
              </InsightList>
            </SectionCard>

            <SectionCard>
              <SectionTitle level={3}>Горячие возможности</SectionTitle>
              <InsightList>
                {supplierInsightsQuery.data.hot_opportunities.length ? (
                  supplierInsightsQuery.data.hot_opportunities.map((item) => (
                    <InsightCard key={item.ste_id}>
                      <InsightTitle>{item.title}</InsightTitle>
                      <InsightMeta>
                        {item.category_name} · {item.supplier_name}
                      </InsightMeta>
                      <InsightMeta>
                        Закупок в истории: {item.purchase_count.toLocaleString('ru-RU')}
                      </InsightMeta>
                    </InsightCard>
                  ))
                ) : (
                  <EmptyState>
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        showOnboarding
                          ? 'Горячие возможности пока не определены.'
                          : 'Горячие позиции пока не определены.'
                      }
                    />
                    <EmptyText>
                      {showOnboarding
                        ? 'После первых поисков и переходов по каталогу здесь появятся позиции с заметным спросом по вашему профилю.'
                        : 'Расширьте поисковые действия в каталоге, чтобы dashboard начал выделять горячие позиции.'}
                    </EmptyText>
                    <Button icon={<AppstoreOutlined />} onClick={() => navigate('/')}>
                      Перейти в каталог
                    </Button>
                  </EmptyState>
                )}
              </InsightList>
            </SectionCard>
          </Grid>
        ) : null}
      </Main>
    </PortalShell>
  )
}

export default SupplierPage
