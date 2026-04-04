import {
  ArrowLeftOutlined,
  AppstoreOutlined,
  RiseOutlined,
  ShoppingCartOutlined,
} from '@ant-design/icons'
import { Button, Empty, Skeleton, Tag, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { Navigate, useNavigate } from 'react-router-dom'
import styled from 'styled-components'
import {
  getCatalogSummary,
  getSupplierInsights,
  type ActorContext,
  type CatalogSummary,
  type SupplierInsightsResponse,
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

function SupplierPage() {
  const session = readStoredSession()
  const navigate = useNavigate()
  const userId = session?.user_id ?? ''
  const actor: ActorContext = { userId }
  const isEnabled = Boolean(session) && session?.role === 'supplier'

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

  if (!session || session.role !== 'supplier') {
    return <Navigate to="/" replace />
  }

  const handleLogout = () => {
    clearStoredSession()
    navigate('/', { replace: true })
  }

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
              Отдельная рабочая зона для анализа конкурентов, категорий спроса и горячих
              возможностей по вашему сегменту.
            </Typography.Paragraph>
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
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Совпавшие поставщики не найдены." />
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
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Спросовые категории пока не определены." />
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
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Конкуренты пока не найдены." />
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
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Горячие позиции пока не определены." />
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
