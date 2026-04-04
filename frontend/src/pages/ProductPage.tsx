import {
  ArrowLeftOutlined,
  HeartFilled,
  HeartOutlined,
  ShoppingCartOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import { Button, Empty, Skeleton, Tag, Typography, message } from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import styled from 'styled-components'
import { formatRelatedReason } from '@entities/search/lib/formatters'
import {
  addCartItem,
  addComparisonItem,
  addFavorite,
  createSearchEvent,
  getCartItems,
  getCatalogItem,
  getComparisonItems,
  getFavorites,
  getRelatedItems,
  removeComparisonItem,
  removeFavorite,
  type ActorContext,
  type CartItem,
  type CatalogItem,
  type ComparisonItem,
  type FavoriteItem,
  type RelatedSearchItem,
} from '@shared/api/search'
import {
  clearStoredSession,
  readLastSearchSessionId,
  readStoredSession,
} from '@shared/lib/portal-session'
import PortalShell from '@widgets/portal-shell/PortalShell'

function buildCardTone(id: string) {
  const tones = [
    ['#f6d79a', '#fff6db'],
    ['#b8cdee', '#eef4ff'],
    ['#d7c4f2', '#f6f1ff'],
    ['#f2c8b8', '#fff3ed'],
    ['#b8e0d3', '#eefbf5'],
  ]
  const index = Math.abs(Array.from(id).reduce((acc, item) => acc + item.charCodeAt(0), 0)) % tones.length
  return tones[index]
}

function buildCardLabel(title: string) {
  return title
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((item) => item[0]?.toUpperCase() ?? '')
    .join('')
}

function buildProductPath(steId: string, sessionId: string | null) {
  return sessionId ? `/product/${steId}?sessionId=${encodeURIComponent(sessionId)}` : `/product/${steId}`
}

const Main = styled.main`
  width: min(1440px, calc(100% - 32px));
  margin: 0 auto;
  padding: 30px 0 40px;

  @media (max-width: 960px) {
    width: min(100%, calc(100% - 20px));
    padding-top: 18px;
  }
`

const HeroCard = styled.section`
  display: grid;
  gap: 20px;
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

const HeroGrid = styled.div`
  display: grid;
  grid-template-columns: 1.1fr minmax(0, 1fr);
  gap: 22px;

  @media (max-width: 980px) {
    grid-template-columns: 1fr;
  }
`

const Visual = styled.div<{ $from: string; $to: string }>`
  position: relative;
  display: grid;
  place-items: center;
  min-height: 360px;
  overflow: hidden;
  border: 1px solid #edf2f7;
  background:
    radial-gradient(circle at 50% 20%, rgba(255, 255, 255, 0.92), transparent 28%),
    linear-gradient(180deg, ${({ $to }) => $to} 0%, #ffffff 36%, #ffffff 100%);

  &::before {
    position: absolute;
    inset: 26px 28px auto;
    height: 190px;
    border-radius: 50%;
    background: radial-gradient(circle, ${({ $from }) => $from} 0%, rgba(255, 255, 255, 0) 70%);
    content: '';
    filter: blur(10px);
    opacity: 0.82;
  }
`

const VisualLabel = styled.span`
  position: relative;
  z-index: 1;
  color: rgba(35, 53, 77, 0.72);
  font-size: 72px;
  font-weight: 800;
  letter-spacing: 0.04em;
`

const Info = styled.div`
  display: grid;
  gap: 16px;
  align-content: start;
`

const MetaGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;

  @media (max-width: 640px) {
    grid-template-columns: 1fr;
  }
`

const MetaCard = styled.div`
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
`

const MetaLabel = styled.span`
  color: #7a889b;
  font-size: 12px;
`

const MetaValue = styled.span`
  color: #2a3f5e;
  font-size: 15px;
  font-weight: 700;
`

const Actions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

const SectionCard = styled.section`
  display: grid;
  gap: 14px;
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

const AttributeGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;

  @media (max-width: 640px) {
    grid-template-columns: 1fr;
  }
`

const AttributeCard = styled.div`
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid #dce4ec;
  background: #fbfcfd;
`

const RelatedGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;

  @media (max-width: 920px) {
    grid-template-columns: 1fr;
  }
`

const RelatedCard = styled.div`
  display: grid;
  gap: 8px;
  padding: 14px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
`

function ProductPage() {
  const session = readStoredSession()
  const { steId } = useParams<{ steId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const trackedRef = useRef<string | null>(null)
  const viewStartRef = useRef<number | null>(null)
  const copyTrackedRef = useRef(false)
  const safeSteId = steId ?? ''
  const userId = session?.user_id ?? ''
  const actor: ActorContext = { userId }
  const sessionId = searchParams.get('sessionId') ?? readLastSearchSessionId()
  const isEnabled = Boolean(session && safeSteId)

  const detailQuery = useQuery<CatalogItem>({
    queryKey: ['catalog-item', safeSteId],
    queryFn: () => getCatalogItem(safeSteId),
    enabled: isEnabled,
  })

  const relatedQuery = useQuery<RelatedSearchItem[]>({
    queryKey: ['related-items', safeSteId],
    queryFn: () => getRelatedItems(safeSteId, 6),
    enabled: isEnabled,
  })

  const favoritesQuery = useQuery<FavoriteItem[]>({
    queryKey: ['favorites', userId],
    queryFn: () => getFavorites(actor),
    enabled: isEnabled,
  })

  const comparisonQuery = useQuery<ComparisonItem[]>({
    queryKey: ['comparison-items', userId],
    queryFn: () => getComparisonItems(actor),
    enabled: isEnabled,
  })

  const cartQuery = useQuery<CartItem[]>({
    queryKey: ['cart-items', userId],
    queryFn: () => getCartItems(actor),
    enabled: isEnabled,
  })

  const favoriteIds = new Set((favoritesQuery.data ?? []).map((item) => item.ste_id))
  const comparisonIds = new Set((comparisonQuery.data ?? []).map((item) => item.ste_id))
  const cartMap = new Map((cartQuery.data ?? []).map((item) => [item.ste_id, item.quantity]))

  useEffect(() => {
    if (!sessionId || !detailQuery.data || trackedRef.current === detailQuery.data.id) {
      return
    }

    trackedRef.current = detailQuery.data.id
    viewStartRef.current = Date.now()
    copyTrackedRef.current = false
    void createSearchEvent({
      session_id: sessionId,
      event_type: 'result_opened',
      ste_id: detailQuery.data.id,
      page_type: 'product',
      page_url: typeof window === 'undefined' ? '' : window.location.pathname,
      payload: { source: 'product_page' },
      actor: { userId },
    })
    void createSearchEvent({
      session_id: sessionId,
      event_type: 'product_view_started',
      ste_id: detailQuery.data.id,
      page_type: 'product',
      page_url: typeof window === 'undefined' ? '' : window.location.pathname,
      actor: { userId },
    })
  }, [detailQuery.data, sessionId, userId])

  useEffect(() => {
    return () => {
      if (!sessionId || !trackedRef.current || !viewStartRef.current) {
        return
      }

      const dwellMs = Math.max(0, Date.now() - viewStartRef.current)
      void createSearchEvent({
        session_id: sessionId,
        event_type: 'product_view_ended',
        ste_id: trackedRef.current,
        page_type: 'product',
        payload: { dwell_ms: dwellMs },
        actor: { userId },
      })
      if (dwellMs < 5000) {
        void createSearchEvent({
          session_id: sessionId,
          event_type: 'quick_back',
          ste_id: trackedRef.current,
          page_type: 'product',
          payload: { dwell_ms: dwellMs },
          actor: { userId },
        })
      }
    }
  }, [sessionId, userId])

  async function invalidateSignals() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['favorites', userId] }),
      queryClient.invalidateQueries({ queryKey: ['comparison-items', userId] }),
      queryClient.invalidateQueries({ queryKey: ['cart-items', userId] }),
      queryClient.invalidateQueries({ queryKey: ['catalog-summary', userId] }),
    ])
  }

  const favoriteMutation = useMutation({
    mutationFn: async ({ active }: { active: boolean }) => {
      if (active) {
        await removeFavorite(safeSteId, actor)
        return
      }
      await addFavorite(safeSteId, actor)
    },
    onSuccess: async (_data, variables) => {
      await invalidateSignals()
      if (sessionId) {
        await createSearchEvent({
          session_id: sessionId,
          event_type: variables.active ? 'favorite_removed' : 'favorite_added',
          ste_id: safeSteId,
          actor: { userId },
        })
      }
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось обновить избранное')
    },
  })

  const comparisonMutation = useMutation({
    mutationFn: async ({ active }: { active: boolean }) => {
      if (active) {
        await removeComparisonItem(safeSteId, actor)
        return
      }
      await addComparisonItem(safeSteId, actor)
    },
    onSuccess: async (_data, variables) => {
      await invalidateSignals()
      if (sessionId) {
        await createSearchEvent({
          session_id: sessionId,
          event_type: variables.active ? 'comparison_removed' : 'comparison_added',
          ste_id: safeSteId,
          actor: { userId },
        })
      }
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось обновить сравнение')
    },
  })

  const cartMutation = useMutation({
    mutationFn: () => addCartItem(safeSteId, 1, actor),
    onSuccess: async () => {
      await invalidateSignals()
      if (sessionId) {
        await createSearchEvent({
          session_id: sessionId,
          event_type: 'cart_added',
          ste_id: safeSteId,
          payload: { quantity: 1 },
          actor: { userId },
        })
      }
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось обновить корзину')
    },
  })

  if (!session || !steId) {
    return <Navigate to="/" replace />
  }

  const [from, to] = buildCardTone(safeSteId)
  const item = detailQuery.data
  const backPath = session.role === 'supplier' ? '/supplier' : '/'
  const handleLogout = () => {
    clearStoredSession()
    navigate('/', { replace: true })
  }

  const handleCopyCapture = () => {
    if (!sessionId || !item || copyTrackedRef.current) {
      return
    }

    const selection = typeof window === 'undefined' ? '' : window.getSelection?.()?.toString().trim() ?? ''
    if (!selection) {
      return
    }

    copyTrackedRef.current = true
    void createSearchEvent({
      session_id: sessionId,
      event_type: 'item_copy',
      ste_id: item.id,
      page_type: 'product',
      payload: {
        selection_length: selection.length,
        copied_text: selection.slice(0, 120),
      },
      actor: { userId },
    })
  }

  const markIrrelevant = () => {
    if (!sessionId || !item) {
      void messageApi.info('Сигнал доступен для позиции, открытой из поисковой выдачи.')
      return
    }

    void createSearchEvent({
      session_id: sessionId,
      event_type: 'irrelevant_marked',
      ste_id: item.id,
      page_type: 'product',
      payload: { source: 'product_page' },
      actor: { userId },
    })
    void messageApi.success('Позиция отмечена как нерелевантная.')
  }

  return (
    <PortalShell session={session} activeNav="catalog" onLogout={handleLogout}>
      {contextHolder}
      <Main onCopyCapture={handleCopyCapture}>
        <HeroCard>
          <HeroTop>
            <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(backPath)}>
              Назад в каталог
            </Button>
            {item ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                <Tag color="blue">{item.category_name}</Tag>
                <Tag>{item.supplier_name}</Tag>
                <Tag color="gold">{item.status}</Tag>
              </div>
            ) : null}
          </HeroTop>

          {detailQuery.isLoading ? (
            <Skeleton active paragraph={{ rows: 10 }} />
          ) : item ? (
            <HeroGrid>
              <Visual $from={from} $to={to}>
                <VisualLabel>{buildCardLabel(item.title)}</VisualLabel>
              </Visual>

              <Info>
                <div style={{ display: 'grid', gap: 8 }}>
                  <Typography.Title level={2} style={{ margin: 0, color: '#2b3950' }}>
                    {item.title}
                  </Typography.Title>
                  <Typography.Paragraph style={{ margin: 0, color: '#607085', fontSize: 16 }}>
                    {item.description}
                  </Typography.Paragraph>
                </div>

                <MetaGrid>
                  <MetaCard>
                    <MetaLabel>ID СТЕ</MetaLabel>
                    <MetaValue>{item.id}</MetaValue>
                  </MetaCard>
                  <MetaCard>
                    <MetaLabel>Поставщик</MetaLabel>
                    <MetaValue>{item.supplier_name}</MetaValue>
                  </MetaCard>
                  <MetaCard>
                    <MetaLabel>Категория</MetaLabel>
                    <MetaValue>{item.category_name}</MetaValue>
                  </MetaCard>
                  <MetaCard>
                    <MetaLabel>Состояние</MetaLabel>
                    <MetaValue>{cartMap.has(item.id) ? 'В закупочной подборке' : item.status}</MetaValue>
                  </MetaCard>
                </MetaGrid>

                <Actions>
                  <Button
                    icon={favoriteIds.has(item.id) ? <HeartFilled /> : <HeartOutlined />}
                    onClick={() =>
                      favoriteMutation.mutate({
                        active: favoriteIds.has(item.id),
                      })
                    }
                  >
                    {favoriteIds.has(item.id) ? 'В избранном' : 'В избранное'}
                  </Button>
                  <Button
                    icon={<SwapOutlined />}
                    onClick={() =>
                      comparisonMutation.mutate({
                        active: comparisonIds.has(item.id),
                      })
                    }
                  >
                    {comparisonIds.has(item.id) ? 'В сравнении' : 'Сравнить'}
                  </Button>
                  <Button type="primary" icon={<ShoppingCartOutlined />} onClick={() => cartMutation.mutate()}>
                    {cartMap.has(item.id) ? 'Добавить ещё' : 'В корзину'}
                  </Button>
                  <Button danger onClick={markIrrelevant}>
                    Нерелевантно
                  </Button>
                </Actions>
              </Info>
            </HeroGrid>
          ) : (
            <Empty description="Позиция не найдена." />
          )}
        </HeroCard>

        {item ? (
          <>
            <SectionCard>
              <SectionTitle level={3}>Характеристики</SectionTitle>
              <AttributeGrid>
                {Object.entries(item.attributes).length ? (
                  Object.entries(item.attributes).map(([key, value]) => (
                    <AttributeCard key={key}>
                      <Typography.Text style={{ color: '#77869a', fontSize: 12 }}>
                        {key}
                      </Typography.Text>
                      <Typography.Text strong>{value}</Typography.Text>
                    </AttributeCard>
                  ))
                ) : (
                  <Typography.Text type="secondary">Характеристики пока не заполнены.</Typography.Text>
                )}
              </AttributeGrid>
            </SectionCard>

            <SectionCard>
              <SectionTitle level={3}>Похожие позиции</SectionTitle>
              {relatedQuery.isLoading ? (
                <Skeleton active paragraph={{ rows: 6 }} />
              ) : (
                <RelatedGrid>
                  {(relatedQuery.data ?? []).length ? (
                    relatedQuery.data?.map((relatedItem) => (
                      <RelatedCard key={relatedItem.id}>
                        <Typography.Text strong>{relatedItem.title}</Typography.Text>
                        <Typography.Text style={{ color: '#647487' }}>
                          {relatedItem.category_name} · {relatedItem.supplier_name}
                        </Typography.Text>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                          {relatedItem.reasons.map((reason) => (
                            <Tag key={reason}>{formatRelatedReason(reason)}</Tag>
                          ))}
                        </div>
                        <div>
                          <Button onClick={() => navigate(buildProductPath(relatedItem.id, sessionId))}>
                            Открыть карточку
                          </Button>
                        </div>
                      </RelatedCard>
                    ))
                  ) : (
                    <Typography.Text type="secondary">Похожие позиции не найдены.</Typography.Text>
                  )}
                </RelatedGrid>
              )}
            </SectionCard>
          </>
        ) : null}
      </Main>
    </PortalShell>
  )
}

export default ProductPage
