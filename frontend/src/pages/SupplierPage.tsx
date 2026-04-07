import {
  ArrowLeftOutlined,
  AppstoreOutlined,
  ShoppingCartOutlined,
} from '@ant-design/icons'
import { Empty, Select, Skeleton } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import styled from 'styled-components'
import {
  activityFilterOptions,
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
import {
  ActivityCard,
  ActivityMeta,
  ActivityText,
  ActivityTimeline,
  ActivityTitle,
  ActivityTop,
  DetailCard,
  DetailList,
  DetailMeta,
  DetailTitle,
  EmptyStateBlock,
  EmptyStateText,
  HeroActionRow,
  HeroEyebrow,
  HeroIntroBlock,
  HeroText,
  HeroTitle,
  MetricCard,
  MetricGrid,
  MetricLabel,
  MetricValue,
  InlineActionRow,
  OnboardingCard,
  OnboardingCardAction,
  OnboardingCardText,
  OnboardingCardTitle,
  OnboardingGrid,
  OnboardingHeader,
  OnboardingSurface,
  OnboardingText,
  OnboardingTitle,
  SectionHeaderBar,
  SectionHeading,
  SectionSurface,
  StatusPill,
  SurfaceButton,
  SnapshotCard,
  SnapshotGrid,
  SnapshotHint,
  SnapshotLabel,
  SnapshotValue,
} from '@shared/ui/dashboard-surfaces'
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

function getActivityPillTone(eventType: string): 'accent' | 'success' | 'warning' | 'danger' | 'purple' | 'info' {
  const normalized = eventType.toLowerCase()
  if (normalized.includes('purchase')) {
    return 'success'
  }
  if (normalized.includes('cart')) {
    return 'warning'
  }
  if (normalized.includes('favorite') || normalized.includes('comparison')) {
    return 'purple'
  }
  if (normalized.includes('irrelevant')) {
    return 'danger'
  }
  if (normalized.includes('result') || normalized.includes('search')) {
    return 'accent'
  }
  return 'info'
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

const HeroBody = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 18px;

  @media (max-width: 1080px) {
    grid-template-columns: 1fr;
  }
`

const HeroTop = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
`

const Actions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
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

const HeroTags = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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
  const entryModeLabel =
    session.entry_mode === 'history'
      ? 'С историей'
      : session.entry_mode === 'context'
      ? 'С контекстом'
      : 'Пустой кабинет'
  const heroDescription =
    session.entry_mode === 'context'
      ? 'Организационный профиль уже подсказывает сегмент, но личная история действий еще не собрана. Запустите готовый сценарий, чтобы быстрее открыть спрос и конкуренцию.'
      : session.entry_mode === 'empty'
        ? 'Новый кабинет поставщика еще без сигналов и поисковой истории. Начните со стартового сценария и соберите первый рыночный срез.'
        : 'Отдельная рабочая зона для анализа конкурентов, категорий спроса и горячих возможностей по вашему сегменту.'

  const openProductCard = (steId: string) => {
    navigate(`/product/${steId}`)
  }

  return (
    <PortalShell session={session} activeNav="supplier" onLogout={handleLogout}>
      <Main>
        <Hero>
          <HeroTop>
            <SurfaceButton $tone="neutral" $emphasis="soft" icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
              Назад в кабинет
            </SurfaceButton>
            <StatusPill $tone="supplier">
              Supplier Dashboard
            </StatusPill>
          </HeroTop>

          <HeroBody>
            <HeroIntroBlock>
              <HeroEyebrow>Контур поставщика</HeroEyebrow>
              <div style={{ display: 'grid', gap: 8 }}>
                <HeroTitle>
                  Экран поставщика
                </HeroTitle>
                <HeroText>
                  {heroDescription}
                </HeroText>
              </div>
              <HeroTags>
                <StatusPill $tone="supplier">{session.persona ?? 'Поставщик'}</StatusPill>
                <StatusPill $tone={session.entry_mode === 'history' ? 'info' : 'warning'}>
                  {entryModeLabel}
                </StatusPill>
              </HeroTags>
              <HeroActionRow>
                <SurfaceButton $tone="neutral" $emphasis="soft" icon={<AppstoreOutlined />} onClick={() => navigate('/')}>
                  Перейти в каталог
                </SurfaceButton>
                <SurfaceButton $tone="accent" $emphasis="soft" icon={<ShoppingCartOutlined />} onClick={() => navigate('/cart')}>
                  Открыть черновик закупки
                </SurfaceButton>
              </HeroActionRow>
            </HeroIntroBlock>

            <SnapshotGrid>
              <SnapshotCard $tone="warm">
                <SnapshotLabel>Режим</SnapshotLabel>
                <SnapshotValue>{entryModeLabel}</SnapshotValue>
                <SnapshotHint>{session.persona ?? 'Сегмент поставщика'}</SnapshotHint>
              </SnapshotCard>
              <SnapshotCard $tone="warm">
                <SnapshotLabel>Стартовый фокус</SnapshotLabel>
                <SnapshotValue>{primaryScenario?.title ?? 'Новый сценарий'}</SnapshotValue>
                <SnapshotHint>
                  {primaryScenario?.description ?? 'Выберите рабочий сценарий для анализа спроса.'}
                </SnapshotHint>
              </SnapshotCard>
              <SnapshotCard $tone="warm">
                <SnapshotLabel>Последние действия</SnapshotLabel>
                <SnapshotValue>{(activityQuery.data?.items ?? []).length.toLocaleString('ru-RU')}</SnapshotValue>
                <SnapshotHint>
                  {(activityQuery.data?.items ?? []).length
                    ? 'Лента активности уже показывает реальные поисковые и закупочные действия.'
                    : 'После первых переходов по каталогу здесь появится рабочая активность.'}
                </SnapshotHint>
              </SnapshotCard>
              <SnapshotCard $tone="warm">
                <SnapshotLabel>Рыночный охват</SnapshotLabel>
                <SnapshotValue>
                  {supplierInsightsQuery.data
                    ? supplierInsightsQuery.data.tracked_categories_count.toLocaleString('ru-RU')
                    : '—'}
                </SnapshotValue>
                <SnapshotHint>Категории, в которых dashboard уже может строить контекст спроса.</SnapshotHint>
              </SnapshotCard>
            </SnapshotGrid>
          </HeroBody>

          {supplierInsightsQuery.isLoading || summaryQuery.isLoading ? (
            <Skeleton active paragraph={{ rows: 6 }} />
          ) : supplierInsightsQuery.data && summaryQuery.data ? (
            <>
              <MetricGrid $columns={4}>
                <MetricCard>
                  <MetricValue $size="lg">
                    {supplierInsightsQuery.data.owned_catalog_items_count.toLocaleString('ru-RU')}
                  </MetricValue>
                  <MetricLabel>Позиции вашего ассортимента</MetricLabel>
                </MetricCard>
                <MetricCard>
                  <MetricValue $size="lg">
                    {supplierInsightsQuery.data.owned_purchase_history_count.toLocaleString('ru-RU')}
                  </MetricValue>
                  <MetricLabel>Закупки по вашему сегменту</MetricLabel>
                </MetricCard>
                <MetricCard>
                  <MetricValue $size="lg">
                    {supplierInsightsQuery.data.tracked_categories_count.toLocaleString('ru-RU')}
                  </MetricValue>
                  <MetricLabel>Категорий под наблюдением</MetricLabel>
                </MetricCard>
                <MetricCard>
                  <MetricValue $size="lg">
                    {summaryQuery.data.suppliers_count.toLocaleString('ru-RU')}
                  </MetricValue>
                  <MetricLabel>Всего поставщиков в каталоге</MetricLabel>
                </MetricCard>
              </MetricGrid>

              <Actions>
                <SurfaceButton $tone="neutral" $emphasis="soft" icon={<AppstoreOutlined />} onClick={() => navigate('/')}>
                  Перейти в каталог
                </SurfaceButton>
                <SurfaceButton $tone="accent" $emphasis="soft" icon={<ShoppingCartOutlined />} onClick={() => navigate('/cart')}>
                  Открыть черновик закупки
                </SurfaceButton>
              </Actions>
            </>
          ) : (
            <Empty description="Supplier analytics пока недоступны." />
          )}
        </Hero>

        {showOnboarding ? (
          <OnboardingSurface $tone="warm" $padding="lg">
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
                  $tone="warm"
                  key={scenario.key}
                  type="button"
                  onClick={() => openStarterScenario(scenario)}
                >
                  <StatusPill $tone="supplier">Сценарий поставщика</StatusPill>
                  <OnboardingCardTitle $tone="warm">{scenario.title}</OnboardingCardTitle>
                  <OnboardingCardText>{scenario.description}</OnboardingCardText>
                  <OnboardingCardAction $tone="warm">Открыть в каталоге</OnboardingCardAction>
                </OnboardingCard>
              ))}
            </OnboardingGrid>
          </OnboardingSurface>
        ) : null}

        <SectionSurface $padding="md" style={{ marginTop: 18 }}>
          <SectionHeaderBar>
            <SectionHeading>Последние действия</SectionHeading>
            <Select
              size="middle"
              value={activityFilter}
              style={{ minWidth: 180 }}
              onChange={(value) => setActivityFilter(value as ActivityFilter)}
              options={activityFilterOptions}
            />
          </SectionHeaderBar>
          {activityQuery.isLoading ? (
            <Skeleton active paragraph={{ rows: 5 }} />
          ) : filteredActivityItems.length ? (
            <ActivityTimeline>
              {filteredActivityItems.map((item: SearchActivityItem) => (
                <ActivityCard key={item.id}>
                  <ActivityTop>
                    <ActivityTitle>{item.title}</ActivityTitle>
                    <span style={{ color: '#7a889b', fontSize: 12 }}>
                      {formatDateTime(item.created_at)}
                    </span>
                  </ActivityTop>
                  <ActivityMeta>
                    <StatusPill $tone={getActivityPillTone(item.event_type)}>{item.event_type}</StatusPill>
                    {item.query ? <StatusPill $tone="neutral">{item.query}</StatusPill> : null}
                    {item.ste_title ? <StatusPill $tone="info">{item.ste_title}</StatusPill> : null}
                  </ActivityMeta>
                  <ActivityText>{item.description}</ActivityText>
                  <InlineActionRow>
                    {item.query ? (
                      <SurfaceButton $tone="neutral" $emphasis="soft" size="small" onClick={() => navigate('/', { state: { starterScenario: {
                        key: `activity-${item.id}`,
                        title: item.query ?? 'Повторный поиск',
                        description: 'Запуск из ленты последних действий.',
                        query: item.query ?? '',
                      } } })}>
                        Повторить поиск
                      </SurfaceButton>
                    ) : null}
                    {item.ste_id ? (
                      <SurfaceButton $tone="accent" $emphasis="soft" size="small" onClick={() => openProductCard(item.ste_id ?? '')}>
                        Открыть карточку
                      </SurfaceButton>
                    ) : null}
                    {(item.event_type === 'cart_added' ||
                      item.event_type === 'cart_removed' ||
                      item.event_type === 'cart_quantity_changed' ||
                      item.event_type === 'purchase_intent' ||
                      item.event_type === 'purchase_completed') ? (
                      <SurfaceButton $tone="success" $emphasis="soft" size="small" onClick={() => navigate('/cart')}>
                        Открыть корзину
                      </SurfaceButton>
                    ) : null}
                  </InlineActionRow>
                </ActivityCard>
              ))}
            </ActivityTimeline>
          ) : (activityQuery.data?.items ?? []).length ? (
            <EmptyStateBlock $padding="compact">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="Для этого типа действий пока нет событий."
              />
              <EmptyStateText>
                Смените фильтр или продолжите работу в каталоге, чтобы собрать новые действия по
                нужному сценарию.
              </EmptyStateText>
              <SurfaceButton $tone="neutral" $emphasis="soft" onClick={() => setActivityFilter('all')}>Показать все действия</SurfaceButton>
            </EmptyStateBlock>
          ) : (
            <EmptyStateBlock $padding="compact">
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="История действий пока пуста."
              />
              <EmptyStateText>
                После первых поисков, открытий карточек и действий с shortlist здесь появится
                живая лента поведения поставщика по текущему сегменту.
              </EmptyStateText>
              {session.entry_note ? <EmptyStateText>{session.entry_note}</EmptyStateText> : null}
              {primaryScenario ? (
                <SurfaceButton $tone="accent" $emphasis="soft" onClick={() => openStarterScenario(primaryScenario)}>
                  Начать со сценария
                </SurfaceButton>
              ) : null}
            </EmptyStateBlock>
          )}
        </SectionSurface>

        {supplierInsightsQuery.isLoading ? (
          <SectionSurface $padding="md" style={{ marginTop: 18 }}>
            <Skeleton active paragraph={{ rows: 10 }} />
          </SectionSurface>
        ) : supplierInsightsQuery.data ? (
          <Grid>
            <SectionSurface $padding="md">
              <SectionHeading>Ваш контур</SectionHeading>
              <DetailList>
                {supplierInsightsQuery.data.matched_suppliers.length ? (
                  supplierInsightsQuery.data.matched_suppliers.map((item) => (
                    <DetailCard key={item.id}>
                      <DetailTitle>{item.name}</DetailTitle>
                      <DetailMeta>
                        Позиций: {item.catalog_items_count.toLocaleString('ru-RU')}
                      </DetailMeta>
                      <DetailMeta>
                        Закупок: {item.purchase_history_count.toLocaleString('ru-RU')}
                      </DetailMeta>
                      <DetailMeta>Overlap токенов: {item.token_overlap}</DetailMeta>
                    </DetailCard>
                  ))
                ) : (
                  <EmptyStateBlock $padding="compact">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        showOnboarding
                          ? 'Совпавшие поставщики пока не найдены.'
                          : 'Совпавшие поставщики не найдены.'
                      }
                    />
                    <EmptyStateText>
                      {showOnboarding
                        ? 'Откройте стартовый сценарий и посмотрите, кто уже присутствует в вашем сегменте.'
                        : 'Попробуйте открыть каталог по смежной категории и проверить конкуренцию вручную.'}
                    </EmptyStateText>
                    {primaryScenario ? (
                      <SurfaceButton $tone="neutral" $emphasis="soft" onClick={() => openStarterScenario(primaryScenario)}>
                        Открыть первый сценарий
                      </SurfaceButton>
                    ) : null}
                  </EmptyStateBlock>
                )}
              </DetailList>
            </SectionSurface>

            <SectionSurface $padding="md">
              <SectionHeading>Спрос по категориям</SectionHeading>
              <DetailList>
                {supplierInsightsQuery.data.top_demand_categories.length ? (
                  supplierInsightsQuery.data.top_demand_categories.map((item) => (
                    <DetailCard key={item.id}>
                      <DetailTitle>{item.name}</DetailTitle>
                      <DetailMeta>
                        Позиций в категории: {item.catalog_items_count.toLocaleString('ru-RU')}
                      </DetailMeta>
                      <DetailMeta>
                        Закупок по истории: {item.purchase_count.toLocaleString('ru-RU')}
                      </DetailMeta>
                    </DetailCard>
                  ))
                ) : (
                  <EmptyStateBlock $padding="compact">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        showOnboarding
                          ? 'Спросовые категории еще не определены.'
                          : 'Спросовые категории пока не определены.'
                      }
                    />
                    <EmptyStateText>
                      {showOnboarding
                        ? 'После первых поисков dashboard сможет показать, где в вашем сегменте есть устойчивый спрос.'
                        : 'Добавьте больше поисковых сигналов через каталог, чтобы расширить категорийный срез.'}
                    </EmptyStateText>
                    {primaryScenario ? (
                      <SurfaceButton $tone="accent" $emphasis="soft" onClick={() => openStarterScenario(primaryScenario)}>
                        Посмотреть спрос в каталоге
                      </SurfaceButton>
                    ) : null}
                  </EmptyStateBlock>
                )}
              </DetailList>
            </SectionSurface>

            <SectionSurface $padding="md">
              <SectionHeading>Топ конкурентов</SectionHeading>
              <DetailList>
                {supplierInsightsQuery.data.top_competitors.length ? (
                  supplierInsightsQuery.data.top_competitors.map((item) => (
                    <DetailCard key={item.id}>
                      <DetailTitle>{item.name}</DetailTitle>
                      <DetailMeta>
                        Позиций в каталоге: {item.catalog_items_count.toLocaleString('ru-RU')}
                      </DetailMeta>
                      <DetailMeta>
                        Закупок в смежных категориях: {item.purchase_history_count.toLocaleString('ru-RU')}
                      </DetailMeta>
                    </DetailCard>
                  ))
                ) : (
                  <EmptyStateBlock $padding="compact">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        showOnboarding ? 'Конкуренты пока не определены.' : 'Конкуренты пока не найдены.'
                      }
                    />
                    <EmptyStateText>
                      {showOnboarding
                        ? 'Готовый сценарий быстро покажет смежных поставщиков и поможет собрать конкурентный контур.'
                        : 'Переключитесь в каталог и проверьте смежные позиции, чтобы обновить конкурентную картину.'}
                    </EmptyStateText>
                    {primaryScenario ? (
                      <SurfaceButton $tone="neutral" $emphasis="soft" onClick={() => openStarterScenario(primaryScenario)}>
                        Открыть конкурентный сценарий
                      </SurfaceButton>
                    ) : null}
                  </EmptyStateBlock>
                )}
              </DetailList>
            </SectionSurface>

            <SectionSurface $padding="md">
              <SectionHeading>Горячие возможности</SectionHeading>
              <DetailList>
                {supplierInsightsQuery.data.hot_opportunities.length ? (
                  supplierInsightsQuery.data.hot_opportunities.map((item) => (
                    <DetailCard key={item.ste_id}>
                      <DetailTitle>{item.title}</DetailTitle>
                      <DetailMeta>
                        {item.category_name} · {item.supplier_name}
                      </DetailMeta>
                      <DetailMeta>
                        Закупок в истории: {item.purchase_count.toLocaleString('ru-RU')}
                      </DetailMeta>
                    </DetailCard>
                  ))
                ) : (
                  <EmptyStateBlock $padding="compact">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description={
                        showOnboarding
                          ? 'Горячие возможности пока не определены.'
                          : 'Горячие позиции пока не определены.'
                      }
                    />
                    <EmptyStateText>
                      {showOnboarding
                        ? 'После первых поисков и переходов по каталогу здесь появятся позиции с заметным спросом по вашему профилю.'
                        : 'Расширьте поисковые действия в каталоге, чтобы dashboard начал выделять горячие позиции.'}
                    </EmptyStateText>
                    <SurfaceButton $tone="neutral" $emphasis="soft" icon={<AppstoreOutlined />} onClick={() => navigate('/')}>
                      Перейти в каталог
                    </SurfaceButton>
                  </EmptyStateBlock>
                )}
              </DetailList>
            </SectionSurface>
          </Grid>
        ) : null}
      </Main>
    </PortalShell>
  )
}

export default SupplierPage
