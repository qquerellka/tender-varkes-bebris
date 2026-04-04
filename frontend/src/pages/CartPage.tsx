import {
  AppstoreOutlined,
  ArrowLeftOutlined,
  DeleteOutlined,
  ShoppingCartOutlined,
} from '@ant-design/icons'
import { Button, Empty, InputNumber, Skeleton, Tag, Typography, message } from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, useNavigate } from 'react-router-dom'
import styled from 'styled-components'
import {
  createPurchase,
  createSearchEvent,
  getCartItems,
  removeCartItem,
  updateCartItem,
  type ActorContext,
  type CartItem,
} from '@shared/api/search'
import {
  clearStoredSession,
  readLastSearchSessionId,
  readStoredSession,
} from '@shared/lib/portal-session'
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

const SectionCard = styled.section`
  display: grid;
  gap: 16px;
  margin-top: 18px;
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

const CartList = styled.div`
  display: grid;
  gap: 14px;
`

const CartCard = styled.article`
  display: grid;
  grid-template-columns: minmax(0, 1fr) 140px 180px;
  gap: 16px;
  align-items: center;
  padding: 16px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;

  @media (max-width: 980px) {
    grid-template-columns: 1fr;
  }
`

const CartInfo = styled.div`
  display: grid;
  gap: 8px;
`

const CartMeta = styled.div`
  color: #627489;
  font-size: 13px;
  line-height: 1.45;
`

const CardActions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;

  @media (max-width: 980px) {
    justify-content: flex-start;
  }
`

const HeroActions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

const EmptyState = styled.div`
  display: grid;
  gap: 14px;
  justify-items: start;
`

const EmptyText = styled.span`
  color: #64748a;
  font-size: 14px;
  line-height: 1.5;
`

const EmptyActions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

type CartStarterScenario = {
  key: string
  title: string
  description: string
  query: string
  categoryId?: string
}

function buildCartStarterScenarios(
  role: string | null | undefined,
  persona: string | null | undefined,
): CartStarterScenario[] {
  const normalizedPersona = persona?.toLowerCase() ?? ''

  if (role === 'supplier') {
    if (normalizedPersona.includes('ит')) {
      return [
        {
          key: 'supplier-it-server',
          title: 'Спрос на серверы',
          description: 'Открывает каталог по серверному сегменту и помогает быстро собрать shortlist.',
          query: 'сервер',
          categoryId: 'cat_it',
        },
        {
          key: 'supplier-it-network',
          title: 'Сетевое оборудование',
          description: 'Подходит для первого конкурентного сценария по смежным позициям.',
          query: 'коммутатор',
          categoryId: 'cat_it',
        },
      ]
    }

    return [
      {
        key: 'supplier-transport-bus',
        title: 'Автобусные закупки',
        description: 'Стартовый транспортный сценарий для наполнения shortlist и черновика.',
        query: 'автобус',
        categoryId: 'cat_transport',
      },
      {
        key: 'supplier-transport-children',
        title: 'Перевозка детей',
        description: 'Узкий кейс, который быстро показывает релевантные позиции.',
        query: 'перевозка детей',
        categoryId: 'cat_transport',
      },
    ]
  }

  if (normalizedPersona.includes('ит')) {
    return [
      {
        key: 'customer-it-server',
        title: 'Серверное оборудование',
        description: 'Быстрый старт по типовой ИТ-закупке.',
        query: 'сервер',
        categoryId: 'cat_it',
      },
      {
        key: 'customer-it-laptop',
        title: 'Рабочие станции',
        description: 'Подходит для наполнения черновика товарами рабочего места.',
        query: 'ноутбук',
        categoryId: 'cat_it',
      },
    ]
  }

  if (normalizedPersona.includes('офис') || normalizedPersona.includes('канцел')) {
    return [
      {
        key: 'customer-office-paper',
        title: 'Бумага и расходники',
        description: 'Открывает типовой офисный сценарий с быстрым наполнением корзины.',
        query: 'бумага',
        categoryId: 'cat_office',
      },
      {
        key: 'customer-office-print',
        title: 'Печать и картриджи',
        description: 'Помогает собрать черновик по оргтехнике и расходникам.',
        query: 'картридж',
        categoryId: 'cat_office',
      },
    ]
  }

  return [
    {
      key: 'customer-transport-bus',
      title: 'Автобусные услуги',
      description: 'Стартовый сценарий для быстрого наполнения корзины и сравнения.',
      query: 'автобус',
      categoryId: 'cat_transport',
    },
    {
      key: 'customer-social-service',
      title: 'Сервисные услуги',
      description: 'Альтернативный сценарий, если нужен сервисный контур вместо товаров.',
      query: 'сопровождение',
      categoryId: 'cat_service',
    },
  ]
}

function CartPage() {
  const session = readStoredSession()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const userId = session?.user_id ?? ''
  const actor: ActorContext = { userId }
  const searchSessionId = readLastSearchSessionId()
  const isEnabled = Boolean(session)

  const cartQuery = useQuery<CartItem[]>({
    queryKey: ['cart-items', userId],
    queryFn: () => getCartItems(actor),
    enabled: isEnabled,
  })

  const updateMutation = useMutation({
    mutationFn: ({ steId, quantity }: { steId: string; quantity: number }) =>
      updateCartItem(steId, quantity, actor),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['cart-items', userId] }),
        queryClient.invalidateQueries({ queryKey: ['catalog-summary', userId] }),
      ])
      if (searchSessionId) {
        await createSearchEvent({
          session_id: searchSessionId,
          event_type: 'cart_quantity_changed',
          ste_id: variables.steId,
          page_type: 'cart',
          payload: { quantity: variables.quantity },
          actor,
        })
      }
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось обновить количество')
    },
  })

  const removeMutation = useMutation({
    mutationFn: (steId: string) => removeCartItem(steId, actor),
    onSuccess: async (_data, steId) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['cart-items', userId] }),
        queryClient.invalidateQueries({ queryKey: ['catalog-summary', userId] }),
      ])
      if (searchSessionId) {
        await createSearchEvent({
          session_id: searchSessionId,
          event_type: 'cart_removed',
          ste_id: steId,
          page_type: 'cart',
          actor,
        })
      }
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось удалить позицию')
    },
  })

  const clearMutation = useMutation({
    mutationFn: async () => {
      const items = cartQuery.data ?? []
      for (const item of items) {
        if (searchSessionId) {
          await createSearchEvent({
            session_id: searchSessionId,
            event_type: 'cart_removed',
            ste_id: item.ste_id,
            page_type: 'cart',
            actor,
          })
        }
        await removeCartItem(item.ste_id, actor)
      }
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['cart-items', userId] }),
        queryClient.invalidateQueries({ queryKey: ['catalog-summary', userId] }),
      ])
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось очистить черновик')
    },
  })

  const purchaseMutation = useMutation({
    mutationFn: async () => {
      const items = cartQuery.data ?? []
      for (const item of items) {
        await createPurchase({
          ste_id: item.ste_id,
          quantity: item.quantity,
          price: 0,
          session_id: searchSessionId ?? undefined,
          actor,
        })
        await removeCartItem(item.ste_id, actor)
      }
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['cart-items', userId] }),
        queryClient.invalidateQueries({ queryKey: ['catalog-summary', userId] }),
        queryClient.invalidateQueries({ queryKey: ['search-profile', userId] }),
      ])
      void messageApi.success('Черновик оформлен как закупка')
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось оформить закупку')
    },
  })

  const items = cartQuery.data ?? []
  const totalQuantity = items.reduce((sum, item) => sum + item.quantity, 0)
  const uniqueCategories = new Set(items.map((item) => item.item.category_name)).size
  const uniqueSuppliers = new Set(items.map((item) => item.item.supplier_name)).size
  const starterScenarios = buildCartStarterScenarios(session?.role, session?.persona)

  if (!session) {
    return <Navigate to="/" replace />
  }

  const backPath = session.role === 'supplier' ? '/supplier' : '/'
  const handleLogout = () => {
    clearStoredSession()
    navigate('/', { replace: true })
  }

  const openStarterScenario = (scenario: CartStarterScenario) => {
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

  return (
    <PortalShell session={session} activeNav="cart" onLogout={handleLogout}>
      {contextHolder}
      <Main>
        <Hero>
          <HeroTop>
            <HeroActions>
              <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(backPath)}>
                Назад в каталог
              </Button>
              <Button
                type="primary"
                disabled={!items.length}
                loading={purchaseMutation.isPending}
                onClick={() => {
                  if (searchSessionId && items.length) {
                    void createSearchEvent({
                      session_id: searchSessionId,
                      event_type: 'purchase_intent',
                      page_type: 'cart',
                      payload: {
                        items_count: items.length,
                        total_quantity: totalQuantity,
                        unique_categories: uniqueCategories,
                        unique_suppliers: uniqueSuppliers,
                      },
                      actor,
                    })
                  }
                  purchaseMutation.mutate()
                }}
              >
                Оформить закупку
              </Button>
            </HeroActions>
            <Tag color="processing" icon={<ShoppingCartOutlined />}>
              Черновик закупки
            </Tag>
          </HeroTop>

          <div style={{ display: 'grid', gap: 8 }}>
            <Typography.Title level={2} style={{ margin: 0, color: '#2b3950' }}>
              Корзина как черновик закупки
            </Typography.Title>
            <Typography.Paragraph style={{ margin: 0, color: '#607085', fontSize: 16 }}>
              Здесь собираются позиции перед дальнейшей закупкой. Количество можно менять на месте,
              а карточки товаров открываются в отдельной странице.
            </Typography.Paragraph>
          </div>

          <SummaryGrid>
            <SummaryCard>
              <SummaryValue>{items.length}</SummaryValue>
              <SummaryLabel>Позиций в черновике</SummaryLabel>
            </SummaryCard>
            <SummaryCard>
              <SummaryValue>{totalQuantity}</SummaryValue>
              <SummaryLabel>Общее количество</SummaryLabel>
            </SummaryCard>
            <SummaryCard>
              <SummaryValue>{uniqueCategories}</SummaryValue>
              <SummaryLabel>Категорий</SummaryLabel>
            </SummaryCard>
            <SummaryCard>
              <SummaryValue>{uniqueSuppliers}</SummaryValue>
              <SummaryLabel>Поставщиков</SummaryLabel>
            </SummaryCard>
          </SummaryGrid>
        </Hero>

        <SectionCard>
          <HeroTop>
            <SectionTitle level={3}>Состав черновика</SectionTitle>
            <Button danger disabled={!items.length} loading={clearMutation.isPending} onClick={() => clearMutation.mutate()}>
              Очистить черновик
            </Button>
          </HeroTop>

          {cartQuery.isLoading ? (
            <Skeleton active paragraph={{ rows: 8 }} />
          ) : items.length ? (
            <CartList>
              {items.map((item) => (
                <CartCard key={item.id}>
                  <CartInfo>
                    <Typography.Title level={4} style={{ margin: 0 }}>
                      {item.item.title}
                    </Typography.Title>
                    <CartMeta>
                      ID СТЕ: {item.item.id} · {item.item.category_name} · {item.item.supplier_name}
                    </CartMeta>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      <Tag color="blue">{item.item.category_name}</Tag>
                      <Tag>{item.item.supplier_name}</Tag>
                    </div>
                  </CartInfo>

                  <InputNumber
                    min={1}
                    max={999}
                    value={item.quantity}
                    style={{ width: '100%' }}
                    onChange={(value) => {
                      if (!value) {
                        return
                      }
                      updateMutation.mutate({
                        steId: item.ste_id,
                        quantity: Number(value),
                      })
                    }}
                  />

                  <CardActions>
                    <Button onClick={() => navigate(`/product/${item.item.id}`)}>Карточка</Button>
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => removeMutation.mutate(item.ste_id)}
                    >
                      Удалить
                    </Button>
                  </CardActions>
                </CartCard>
              ))}
            </CartList>
          ) : (
            <EmptyState>
              <Empty description="Черновик закупки пуст. Добавьте позиции из каталога или карточки товара." />
              <EmptyText>
                {session.entry_mode === 'empty' || session.entry_mode === 'context'
                  ? 'Для нового кабинета проще всего начать с готового сценария: откройте каталог, добавьте несколько позиций и вернитесь сюда для оформления черновика.'
                  : 'Откройте каталог, найдите нужные позиции и соберите здесь рабочий черновик закупки.'}
              </EmptyText>
              <EmptyActions>
                <Button icon={<AppstoreOutlined />} onClick={() => navigate('/')}>
                  Перейти в каталог
                </Button>
                {starterScenarios.map((scenario) => (
                  <Button
                    key={scenario.key}
                    type="primary"
                    ghost
                    onClick={() => openStarterScenario(scenario)}
                  >
                    {scenario.title}
                  </Button>
                ))}
              </EmptyActions>
            </EmptyState>
          )}
        </SectionCard>
      </Main>
    </PortalShell>
  )
}

export default CartPage
