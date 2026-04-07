import {
  ArrowLeftOutlined,
  HeartFilled,
  HeartOutlined,
  ShoppingCartOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import { Empty, Skeleton, Typography, message } from 'antd'
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
import {
  DetailCard,
  DetailMeta,
  DetailTitle,
  HintSurface,
  HintText,
  SectionHeading,
  SectionSurface,
  StatusPill,
  SurfaceButton,
} from '@shared/ui/dashboard-surfaces'
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
  gap: 18px;
  align-content: start;
`

const ContextRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`

const ContextChip = styled.span<{ $tone?: 'neutral' | 'accent' | 'success' | 'warning' }>`
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border: 1px solid
    ${({ $tone = 'neutral' }) =>
      $tone === 'accent'
        ? '#cfdcf0'
        : $tone === 'success'
        ? '#cfe6da'
        : $tone === 'warning'
        ? '#eadac0'
        : '#dde5ee'};
  color: ${({ $tone = 'neutral' }) =>
    $tone === 'accent'
      ? '#2f4f84'
      : $tone === 'success'
      ? '#226246'
      : $tone === 'warning'
      ? '#7a5a1d'
      : '#5e6f84'};
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: ${({ $tone = 'neutral' }) =>
    $tone === 'accent'
      ? '#f3f7fd'
      : $tone === 'success'
      ? '#eef8f2'
      : $tone === 'warning'
      ? '#fff8ea'
      : '#f8fbfe'};
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
  gap: 3px;
  padding: 12px 14px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
`

const MetaLabel = styled.span`
  color: #7c8a9b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
`

const MetaValue = styled.span`
  color: #31455f;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.45;
`

const Actions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
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
  gap: 3px;
  padding: 12px 14px;
  border: 1px solid #dce4ec;
  background: #fbfcfd;
`

const RelatedGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;

  @media (max-width: 1200px) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  @media (max-width: 920px) {
    grid-template-columns: 1fr;
  }
`

const RelatedCard = styled.div`
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: 10px;
  padding: 14px;
  border: 1px solid #e1e8f0;
  background: #fbfcfe;
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
`

const RelatedTop = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
`

const RelatedStamp = styled.span`
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 6px 10px;
  border: 1px solid #d7e1ec;
  color: #58708f;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: #f8fbfe;
`

const RelatedVisual = styled.button<{ $from: string; $to: string }>`
  position: relative;
  display: grid;
  place-items: center;
  min-height: 150px;
  overflow: hidden;
  border: 1px solid #edf2f7;
  background:
    radial-gradient(circle at 50% 20%, rgba(255, 255, 255, 0.9), transparent 28%),
    linear-gradient(180deg, ${({ $to }) => $to} 0%, #ffffff 42%, #ffffff 100%);
  cursor: pointer;

  &::before {
    position: absolute;
    inset: 18px 24px auto;
    height: 96px;
    border-radius: 50%;
    background: radial-gradient(circle, ${({ $from }) => $from} 0%, rgba(255, 255, 255, 0) 70%);
    content: '';
    filter: blur(8px);
    opacity: 0.78;
  }
`

const RelatedVisualLabel = styled.span`
  position: relative;
  z-index: 1;
  color: rgba(35, 53, 77, 0.72);
  font-size: 42px;
  font-weight: 800;
  letter-spacing: 0.04em;
`

const RelatedTitle = styled.button`
  padding: 0;
  border: 0;
  color: #2f3b4c;
  font: inherit;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.45;
  text-align: left;
  background: transparent;
  cursor: pointer;
`

const RelatedMeta = styled.div`
  display: grid;
  gap: 8px;
`

const RelatedMetaCard = styled.div`
  display: grid;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid #e1e8f0;
  background: #ffffff;
`

const RelatedMetaLabel = styled.span`
  color: #7c8a9b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
`

const RelatedMetaValue = styled.span`
  color: #31455f;
  font-size: 13px;
  line-height: 1.45;
`

const RelatedReasonPanel = styled.div`
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid #dce5ee;
  background: linear-gradient(180deg, #fbfcfe 0%, #ffffff 100%);
`

const RelatedReasonHeader = styled.div`
  color: #405672;
  font-size: 12px;
  font-weight: 700;
`

const RelatedReasonList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`

const RelatedReasonChip = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-left: 3px solid #2f4f84;
  color: #596a7f;
  font-size: 12px;
  line-height: 1.35;
  background: #f6f9fd;
`

const RelatedActions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

const ExplainabilitySummary = styled.div`
  display: grid;
  gap: 10px;
`

function buildExplainabilityNotes(
  entryMode: string | null | undefined,
  item: CatalogItem,
  state: { inFavorites: boolean; inComparison: boolean; inCart: boolean; hasSessionContext: boolean },
) {
  const notes = [
    entryMode === 'empty'
      ? {
          title: 'Один из первых сигналов профиля',
          text: `Карточка помогает новому кабинету собрать первый рабочий контекст по категории "${item.category_name}" и поставщику "${item.supplier_name}".`,
        }
      : entryMode === 'context'
      ? {
          title: 'Релевантность строится на организационном контексте',
          text: `Личная история еще не накоплена, поэтому эта позиция особенно полезна как отправная точка для сегмента "${item.category_name}".`,
        }
      : {
          title: 'Карточка усиливает существующий профиль',
          text: `Эта позиция дополняет уже накопленные сигналы пользователя и помогает уточнить интерес к сегменту "${item.category_name}".`,
        },
    state.inFavorites
      ? {
          title: 'Позиция сохранена в shortlist',
          text: 'Избранное зафиксировало явный интерес к карточке, поэтому к ней можно быстро вернуться из кабинета.',
        }
      : {
          title: 'Сигнал еще не закреплен',
          text: 'Если карточка подходит, добавьте ее в избранное или сравнение, чтобы система считала ее устойчивым интересом.',
        },
    state.inCart
      ? {
          title: 'Карточка уже в закупочном черновике',
          text: 'Позиция участвует в рабочем подборе и напрямую влияет на дальнейший профиль действий пользователя.',
        }
      : state.inComparison
      ? {
          title: 'Карточка участвует в сравнении',
          text: 'Вы уже отправили позицию в compare-flow. Следующий полезный шаг: проверить соседние карточки и собрать shortlist.',
        }
      : {
          title: state.hasSessionContext ? 'Есть поисковый контекст' : 'Контекст еще собирается',
          text: state.hasSessionContext
            ? 'Карточка открыта в рамках активной поисковой сессии, поэтому действия на ней попадут в explainability и telemetry пользователя.'
            : 'Откройте карточку из каталога после поиска или добавьте позицию в корзину, чтобы связать ее с рабочим сценарием пользователя.',
        },
  ]

  return notes
}

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
  const inFavorites = item ? favoriteIds.has(item.id) : false
  const inComparison = item ? comparisonIds.has(item.id) : false
  const inCart = item ? cartMap.has(item.id) : false
  const explainabilityNotes = item
    ? buildExplainabilityNotes(session.entry_mode, item, {
        inFavorites,
        inComparison,
        inCart,
        hasSessionContext: Boolean(sessionId),
      })
    : []
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
            <SurfaceButton $tone="neutral" $emphasis="soft" icon={<ArrowLeftOutlined />} onClick={() => navigate(backPath)}>
              Назад в каталог
            </SurfaceButton>
            {item ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                <StatusPill $tone="info">{item.category_name}</StatusPill>
                <StatusPill $tone="neutral">{item.supplier_name}</StatusPill>
                <StatusPill $tone="warning">{item.status}</StatusPill>
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

                <ContextRow>
                  <ContextChip $tone="neutral">ID {item.id}</ContextChip>
                  <ContextChip $tone="accent">
                    {session.entry_mode === 'history'
                      ? 'С историей'
                      : session.entry_mode === 'context'
                      ? 'С контекстом'
                      : 'Пустой кабинет'}
                  </ContextChip>
                  {inFavorites ? <ContextChip $tone="accent">Избранное</ContextChip> : null}
                  {inComparison ? <ContextChip $tone="warning">Сравнение</ContextChip> : null}
                  {inCart ? <ContextChip $tone="success">В корзине</ContextChip> : null}
                </ContextRow>

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
                    <MetaValue>{inCart ? 'В закупочной подборке' : item.status}</MetaValue>
                  </MetaCard>
                </MetaGrid>

                <HintSurface>
                  <HintText>
                    {session.role === 'supplier'
                      ? 'Карточка продолжает supplier-контур: здесь видно, насколько позиция полезна для конкурентного анализа и рыночного спроса.'
                      : 'Карточка продолжает product-card из каталога: здесь можно закрепить позицию в shortlist, compare-flow и закупочном черновике.'}
                  </HintText>
                  <HintText>
                    {inCart
                      ? 'Позиция уже влияет на рабочий подбор. Следующий полезный шаг: проверить похожие карточки и сравнить их по параметрам.'
                      : inComparison
                      ? 'Позиция уже участвует в сравнении. Можно быстро проверить похожие карточки ниже и усилить shortlist.'
                      : 'Если позиция подходит, закрепите ее в избранном, сравнении или корзине, чтобы это стало явным рабочим сигналом.'}
                  </HintText>
                </HintSurface>

                <Actions>
                  <SurfaceButton
                    $tone={inFavorites ? 'accent' : 'neutral'}
                    $emphasis={inFavorites ? 'soft' : 'outline'}
                    icon={inFavorites ? <HeartFilled /> : <HeartOutlined />}
                    onClick={() =>
                      favoriteMutation.mutate({
                        active: inFavorites,
                      })
                    }
                  >
                    {inFavorites ? 'В избранном' : 'В избранное'}
                  </SurfaceButton>
                  <SurfaceButton
                    $tone={inComparison ? 'accent' : 'neutral'}
                    $emphasis={inComparison ? 'soft' : 'outline'}
                    icon={<SwapOutlined />}
                    onClick={() =>
                      comparisonMutation.mutate({
                        active: inComparison,
                      })
                    }
                  >
                    {inComparison ? 'В сравнении' : 'Сравнить'}
                  </SurfaceButton>
                  <SurfaceButton $tone={inCart ? 'success' : 'accent'} $emphasis={inCart ? 'soft' : 'solid'} icon={<ShoppingCartOutlined />} onClick={() => cartMutation.mutate()}>
                    {inCart ? 'Добавить ещё' : 'В корзину'}
                  </SurfaceButton>
                  <SurfaceButton $tone="danger" $emphasis="soft" onClick={markIrrelevant}>
                    Нерелевантно
                  </SurfaceButton>
                </Actions>
              </Info>
            </HeroGrid>
          ) : (
            <Empty description="Позиция не найдена." />
          )}
        </HeroCard>

        {item ? (
          <>
            <SectionSurface $padding="md" style={{ marginTop: 18 }}>
              <SectionHeading>Почему карточка может быть полезна</SectionHeading>
              <HintSurface>
                <HintText>
                  {session.role === 'supplier'
                    ? 'Для поставщика карточка помогает оценить смежный спрос, конкурентов и то, насколько позиция вписывается в рабочий сегмент.'
                    : 'Для заказчика карточка помогает понять, подходит ли позиция под текущий сценарий закупки и стоит ли закрепить ее в shortlist.'}
                </HintText>
                {session.entry_note ? <HintText>{session.entry_note}</HintText> : null}
                <ContextRow>
                  <StatusPill $tone={session.entry_mode === 'history' ? 'info' : 'warning'}>
                    {session.entry_mode === 'history'
                      ? 'С историей'
                      : session.entry_mode === 'context'
                      ? 'С контекстом'
                      : 'Пустой кабинет'}
                  </StatusPill>
                  {inFavorites ? <StatusPill $tone="purple">В избранном</StatusPill> : null}
                  {inComparison ? <StatusPill $tone="purple">В сравнении</StatusPill> : null}
                  {inCart ? <StatusPill $tone="success">В корзине</StatusPill> : null}
                </ContextRow>
              </HintSurface>
              <ExplainabilitySummary>
                {explainabilityNotes.map((note) => (
                  <DetailCard key={note.title}>
                    <DetailTitle>{note.title}</DetailTitle>
                    <DetailMeta>{note.text}</DetailMeta>
                  </DetailCard>
                ))}
              </ExplainabilitySummary>
              <Actions>
                <SurfaceButton $tone="neutral" $emphasis="soft" onClick={() => navigate(backPath)}>Вернуться к выдаче</SurfaceButton>
                <SurfaceButton $tone="accent" $emphasis="soft" onClick={() => navigate('/cart')}>Открыть корзину</SurfaceButton>
              </Actions>
            </SectionSurface>

            <SectionSurface $padding="md" style={{ marginTop: 18 }}>
              <SectionHeading>Характеристики</SectionHeading>
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
            </SectionSurface>

            <SectionSurface $padding="md" style={{ marginTop: 18 }}>
              <SectionHeading>Похожие позиции</SectionHeading>
              {relatedQuery.isLoading ? (
                <Skeleton active paragraph={{ rows: 6 }} />
              ) : (
                <RelatedGrid>
                  {(relatedQuery.data ?? []).length ? (
                    relatedQuery.data?.map((relatedItem) => {
                      const [relatedFrom, relatedTo] = buildCardTone(relatedItem.id)
                      return (
                        <RelatedCard key={relatedItem.id}>
                          <RelatedTop>
                            <RelatedStamp>ID СТЕ {relatedItem.id}</RelatedStamp>
                            <StatusPill $tone="accent">Похожая позиция</StatusPill>
                          </RelatedTop>
                          <RelatedVisual
                            type="button"
                            $from={relatedFrom}
                            $to={relatedTo}
                            onClick={() => navigate(buildProductPath(relatedItem.id, sessionId))}
                          >
                            <RelatedVisualLabel>{buildCardLabel(relatedItem.title)}</RelatedVisualLabel>
                          </RelatedVisual>
                          <RelatedTitle
                            type="button"
                            onClick={() => navigate(buildProductPath(relatedItem.id, sessionId))}
                          >
                            {relatedItem.title}
                          </RelatedTitle>
                          <RelatedMeta>
                            <RelatedMetaCard>
                              <RelatedMetaLabel>Категория</RelatedMetaLabel>
                              <RelatedMetaValue>{relatedItem.category_name}</RelatedMetaValue>
                            </RelatedMetaCard>
                            <RelatedMetaCard>
                              <RelatedMetaLabel>Поставщик</RelatedMetaLabel>
                              <RelatedMetaValue>{relatedItem.supplier_name}</RelatedMetaValue>
                            </RelatedMetaCard>
                          </RelatedMeta>
                          <RelatedReasonPanel>
                            <RelatedReasonHeader>Почему карточка показана</RelatedReasonHeader>
                            <RelatedReasonList>
                              {relatedItem.reasons.map((reason) => (
                                <RelatedReasonChip key={reason}>
                                  {formatRelatedReason(reason)}
                                </RelatedReasonChip>
                              ))}
                            </RelatedReasonList>
                          </RelatedReasonPanel>
                          <RelatedActions>
                            <SurfaceButton $tone="neutral" $emphasis="soft" onClick={() => navigate(buildProductPath(relatedItem.id, sessionId))}>
                              Открыть карточку
                            </SurfaceButton>
                          </RelatedActions>
                        </RelatedCard>
                      )
                    })
                  ) : (
                    <HintSurface>
                      <HintText>
                        Похожие позиции пока не найдены. Это нормально для нового или узкого
                        сценария: закрепите карточку в избранном, сравнении или корзине, чтобы
                        быстрее собрать смежный контекст.
                      </HintText>
                      <Actions>
                        <SurfaceButton
                          $tone={inFavorites ? 'success' : 'accent'}
                          $emphasis="soft"
                          onClick={() =>
                            favoriteMutation.mutate({
                              active: inFavorites,
                            })
                          }
                        >
                          {inFavorites ? 'Уже в избранном' : 'Добавить в избранное'}
                        </SurfaceButton>
                        <SurfaceButton $tone="neutral" $emphasis="soft" onClick={() => navigate(backPath)}>Назад к каталогу</SurfaceButton>
                      </Actions>
                    </HintSurface>
                  )}
                </RelatedGrid>
              )}
            </SectionSurface>
          </>
        ) : null}
      </Main>
    </PortalShell>
  )
}

export default ProductPage
