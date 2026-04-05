import {
  AppstoreOutlined,
  HeartFilled,
  HeartOutlined,
  SearchOutlined,
  ShoppingCartOutlined,
  StarOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import {
  AutoComplete,
  Badge,
  Button,
  Empty,
  Input,
  Pagination,
  Select,
  Skeleton,
  Tag,
  Typography,
  message,
} from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import styled from 'styled-components'
import {
  activityFilterOptions,
  getActivityFilterKey,
  type ActivityFilter,
} from '@entities/search/lib/activity'
import { buildAutocompleteOptions, formatSearchReason } from '@entities/search/lib/formatters'
import {
  addCartItem,
  addComparisonItem,
  addFavorite,
  clearSearchHistory,
  createSearchEvent,
  createSearchImpressions,
  getCustomerAccounts,
  getCartItems,
  getCategories,
  getSearchActivity,
  getCatalogFeed,
  getCatalogSummary,
  getComparisonItems,
  getDemoUsers,
  getFavorites,
  getPurchaseHistory,
  getProductionOrigins,
  getSearchHistory,
  getSearchProfile,
  getSearchSuggestions,
  getSupplierInsights,
  getSuppliers,
  loginCustomerByInn,
  loginDemoUser,
  removeComparisonItem,
  removeFavorite,
  searchCatalog,
  type ActorContext,
  type AuthSession,
  type CartItem,
  type CatalogCategory,
  type CatalogFeedResponse,
  type CatalogSummary,
  type CatalogSupplier,
  type ComparisonItem,
  type CustomerInnAccount,
  type FavoriteItem,
  type ProductionOriginOption,
  type PurchaseHistoryItem,
  type SearchHistoryItem,
  type SearchActivityItem,
  type SearchProfileResponse,
  type SearchResponse,
  type SupplierInsightsResponse,
} from '@shared/api/search'
import {
  clearStoredSession,
  readStoredSession,
  writeLastSearchSessionId,
  writeStoredSession,
} from '@shared/lib/portal-session'
import {
  ActivityCard,
  ActivityMeta,
  ActivityText,
  ActivityTimeline,
  ActivityTitle,
  ActivityTop,
  HintSurface,
  HintText,
  EmptyStateBlock,
  EmptyStateText,
  HeroActionRow,
  HeroEyebrow,
  HeroIntroBlock,
  HeroText,
  HeroTitle,
  InlineActionRow,
  MetricCard,
  MetricGrid,
  MetricLabel,
  MetricValue,
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
  SectionHeadingHint,
  SectionHeadingStack,
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

const STORAGE_KEYS = {
  search: 'portal-search-query-v2',
  category: 'portal-search-category-v2',
  supplier: 'portal-search-supplier-v2',
  origin: 'portal-search-origin-v1',
  domestic: 'portal-search-domestic-v1',
  strict: 'portal-search-strict-v2',
  sort: 'portal-search-sort-v1',
} as const

const CATALOG_PAGE_SIZE = 18
const FAVORITES_PAGE_SIZE = 18
const RESULTS_SCROLL_OFFSET = 104

type WorkspaceTab = 'catalog' | 'favorites' | 'compare'
type SortMode = 'relevance' | 'title_asc' | 'supplier_asc'
type StarterScenario = {
  key: string
  title: string
  description: string
  query: string
  categoryId?: string
  strictMatch?: boolean
}

type SearchState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'results'; response: SearchResponse }

function readStoredValue(key: string): string {
  if (typeof window === 'undefined') {
    return ''
  }

  return window.localStorage.getItem(key) ?? ''
}

function formatPurchasePrice(value: string) {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) {
    return value
  }

  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(numericValue)
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

function formatPurchaseDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(value))
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

function buildStarterScenarios(session: AuthSession): StarterScenario[] {
  const persona = session.persona?.toLowerCase() ?? ''

  if (session.role === 'supplier') {
    if (persona.includes('ит')) {
      return [
        {
          key: 'supplier-it-server',
          title: 'Спрос на серверы',
          description: 'Проверьте конкурентную выдачу и активный спрос по серверной категории.',
          query: 'сервер',
          categoryId: 'cat_it',
        },
        {
          key: 'supplier-it-network',
          title: 'Сетевое оборудование',
          description: 'Посмотрите, как в каталоге выглядят смежные позиции и поставщики.',
          query: 'коммутатор',
          categoryId: 'cat_it',
        },
        {
          key: 'supplier-it-support',
          title: 'Сервисный сегмент',
          description: 'Откройте рынок сопровождения и сравните сервисные предложения.',
          query: 'техническая поддержка',
          categoryId: 'cat_service',
        },
      ]
    }

    if (persona.includes('офис') || persona.includes('канцел')) {
      return [
        {
          key: 'supplier-office-paper',
          title: 'Канцелярский спрос',
          description: 'Быстрый вход в сегмент бумаги, расходников и типовых офисных закупок.',
          query: 'бумага',
          categoryId: 'cat_office',
        },
        {
          key: 'supplier-office-furniture',
          title: 'Офисная мебель',
          description: 'Проверьте мебельный сегмент и предложения по оснащению рабочих мест.',
          query: 'офисная мебель',
          categoryId: 'cat_office',
        },
        {
          key: 'supplier-office-print',
          title: 'Расходники для печати',
          description: 'Посмотрите выдачу по картриджам и оргтехнике без ручной настройки.',
          query: 'картридж',
          categoryId: 'cat_office',
        },
      ]
    }

    if (persona.includes('услуг') || persona.includes('сопровожд')) {
      return [
        {
          key: 'supplier-service-support',
          title: 'Сопровождение систем',
          description: 'Откройте сегмент сопровождения и эксплуатации услуг.',
          query: 'сопровождение системы',
          categoryId: 'cat_service',
        },
        {
          key: 'supplier-service-cleaning',
          title: 'Клининг и facility',
          description: 'Быстрый просмотр категории регулярных сервисных контрактов.',
          query: 'клининг',
          categoryId: 'cat_service',
        },
        {
          key: 'supplier-service-office',
          title: 'Офисные услуги',
          description: 'Проверьте смежную выдачу по поддержке офисной инфраструктуры.',
          query: 'обслуживание офиса',
          categoryId: 'cat_service',
        },
      ]
    }

    return [
      {
        key: 'supplier-transport-bus',
        title: 'Рынок автобусных закупок',
        description: 'Стартовый запрос по основному сегменту пассажирского транспорта.',
        query: 'автобус',
        categoryId: 'cat_transport',
      },
      {
        key: 'supplier-transport-children',
        title: 'Перевозка детей',
        description: 'Показывает более узкий закупочный кейс с понятной конкуренцией.',
        query: 'перевозка детей',
        categoryId: 'cat_transport',
      },
      {
        key: 'supplier-transport-microbus',
        title: 'Микроавтобусы',
        description: 'Откройте смежный транспортный сегмент без ручного фильтра.',
        query: 'микроавтобус',
        categoryId: 'cat_transport',
      },
    ]
  }

  if (persona.includes('ит')) {
    return [
      {
        key: 'customer-it-server',
        title: 'Серверное оборудование',
        description: 'Начните с типовой ИТ-закупки и сразу получите предметную выдачу.',
        query: 'сервер',
        categoryId: 'cat_it',
      },
      {
        key: 'customer-it-laptop',
        title: 'Рабочие станции',
        description: 'Быстрый сценарий для закупки ноутбуков и техники рабочих мест.',
        query: 'ноутбук',
        categoryId: 'cat_it',
      },
      {
        key: 'customer-it-support',
        title: 'Поддержка инфраструктуры',
        description: 'Откройте сервисный сценарий по сопровождению и эксплуатации ИТ.',
        query: 'обслуживание серверов',
        categoryId: 'cat_service',
      },
    ]
  }

  if (persona.includes('соц') || persona.includes('услуг')) {
    return [
      {
        key: 'customer-social-service',
        title: 'Услуги сопровождения',
        description: 'Подходит для старта нового кабинета без поисковой истории.',
        query: 'сопровождение',
        categoryId: 'cat_service',
      },
      {
        key: 'customer-social-cleaning',
        title: 'Клининг помещений',
        description: 'Быстрый сценарий по регулярным услугам и facility-контексту.',
        query: 'клининг',
        categoryId: 'cat_service',
      },
      {
        key: 'customer-social-office',
        title: 'Офисное снабжение',
        description: 'Смежный сценарий для расходников и обеспечения рабочих мест.',
        query: 'бумага',
        categoryId: 'cat_office',
      },
    ]
  }

  if (persona.includes('офис') || persona.includes('канцел')) {
    return [
      {
        key: 'customer-office-paper',
        title: 'Бумага и расходники',
        description: 'Запускает первый сценарий закупки по офисному снабжению.',
        query: 'бумага',
        categoryId: 'cat_office',
      },
      {
        key: 'customer-office-furniture',
        title: 'Мебель для рабочих мест',
        description: 'Подбирает мебельный сегмент и смежные позиции каталога.',
        query: 'офисные кресла',
        categoryId: 'cat_office',
      },
      {
        key: 'customer-office-print',
        title: 'Печать и картриджи',
        description: 'Стартовый сценарий по оргтехнике и расходным материалам.',
        query: 'картридж',
        categoryId: 'cat_office',
      },
    ]
  }

  return [
    {
      key: 'customer-transport-bus',
      title: 'Автобусные услуги',
      description: 'Запускает понятный транспортный кейс и сразу показывает выдачу.',
      query: 'автобус',
      categoryId: 'cat_transport',
    },
    {
      key: 'customer-transport-children',
      title: 'Перевозка детей',
      description: 'Более узкий закупочный сценарий с хорошей демонстрацией поиска.',
      query: 'перевозка детей',
      categoryId: 'cat_transport',
    },
    {
      key: 'customer-transport-office',
      title: 'Офисное снабжение',
      description: 'Смежный сценарий, если хотите быстро наполнить профиль сигналами.',
      query: 'бумага',
      categoryId: 'cat_office',
    },
  ]
}

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

const Screen = styled.div`
  min-height: 100vh;
  background:
    linear-gradient(180deg, #f5f6f8 0%, #eef2f5 26%, #f6f7f9 100%);
  color: #223047;
`

const Brand = styled.div`
  display: flex;
  align-items: center;
  min-width: 0;
`

const BrandLogo = styled.img`
  display: block;
  width: auto;
  max-width: min(100%, 280px);
  height: 60px;
  object-fit: contain;

  @media (max-width: 960px) {
    height: 50px;
  }
`

const HeaderTools = styled.div`
  display: flex;
  align-items: stretch;
  gap: 0;
  border-left: 1px solid #e1e6ec;

  @media (max-width: 1180px) {
    display: none;
  }
`

const HeaderTool = styled.button`
  display: grid;
  place-items: center;
  width: 64px;
  border: 0;
  border-right: 1px solid #e1e6ec;
  color: #355887;
  background: transparent;
  cursor: pointer;

  &:hover {
    background: #f5f9ff;
  }
`

const Main = styled.main`
  width: min(1440px, calc(100% - 32px));
  margin: 0 auto;
  padding: 30px 0 40px;

  @media (max-width: 960px) {
    width: min(100%, calc(100% - 20px));
    padding-top: 18px;
  }
`

const SearchStrip = styled.section`
  display: grid;
  gap: 18px;
  padding: 22px 24px;
  border: 1px solid #d8e0e8;
  background: #fff;
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
`

const SearchHeroTop = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 18px;

  @media (max-width: 1080px) {
    grid-template-columns: 1fr;
  }
`

const SearchRow = styled.div`
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) 160px;
  gap: 14px;
  align-items: center;

  @media (max-width: 1080px) {
    grid-template-columns: 1fr;
  }
`

const CatalogButton = styled(Button)`
  &.ant-btn {
    height: 48px;
    border-radius: 0;
    border-color: #2f4f84;
    color: #2f4f84;
    font-weight: 700;
    justify-content: flex-start;
  }
`

const SearchInputWrap = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 1fr) 50px;
  border: 1px solid #d4dce6;

  @media (max-width: 1080px) {
    grid-template-columns: minmax(0, 1fr) 56px;
  }
`

const SearchAutocomplete = styled(AutoComplete)`
  width: 100%;

  .ant-select-selector {
    padding: 0 !important;
    border: 0 !important;
    box-shadow: none !important;
    border-radius: 0 !important;
  }
`

const SearchField = styled(Input)`
  &.ant-input {
    height: 48px;
    border: 0;
    border-radius: 0;
    color: #1e2f47;
    font-size: 15px;
  }
`

const SearchSubmit = styled(Button)`
  &.ant-btn {
    height: 48px;
    border: 0;
    border-left: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 0;
    background: #cb3428;
    box-shadow: none;
  }
`

const SearchMetaRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
`

const CollectionActionRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

const SearchMetaGroup = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
`

const WorkspaceGrid = styled.section`
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 22px;
  margin-top: 22px;

  @media (max-width: 1160px) {
    grid-template-columns: 1fr;
  }
`

const Sidebar = styled.aside`
  display: grid;
  gap: 18px;
  align-self: start;
`

const SidebarCard = styled.section`
  display: grid;
  gap: 14px;
  padding: 20px;
  border: 1px solid #d9e0e8;
  background: #fff;
`

const SidebarHeader = styled.div`
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
`

const ActivityControls = styled.div`
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
`

const SidebarTitle = styled(Typography.Title)`
  && {
    margin: 0;
    color: #2f3a4d;
    font-size: 17px;
    font-weight: 700;
  }
`

const SidebarSubtitle = styled(Typography.Text)`
  color: #667487;
  font-size: 12px;
`

const FilterStack = styled.div`
  display: grid;
  gap: 10px;
`

const FilterLabel = styled.div`
  color: #30415a;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
`

const FilterField = styled.div`
  display: grid;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px solid #edf1f5;
`

const FilterMetaCard = styled.div`
  padding: 12px 14px;
  border: 1px solid #e2e8ef;
  color: #5d6f84;
  background: #f8fbfe;
  font-size: 13px;
  line-height: 1.45;
`

const SignalList = styled.div`
  display: grid;
  gap: 10px;
`

const SignalCard = styled.div`
  padding: 12px 14px;
  border-left: 3px solid #2f4f84;
  background: #f6f9fd;
  color: #54657a;
  font-size: 13px;
  line-height: 1.45;
`

const PurchaseList = styled.div`
  display: grid;
  gap: 10px;
`

const PurchaseCard = styled.div`
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid #e2e8ef;
  background: #fbfcfd;
`

const PurchaseTitle = styled.span`
  color: #273a53;
  font-size: 14px;
  font-weight: 700;
`

const PurchaseMeta = styled.span`
  color: #6f7d8e;
  font-size: 12px;
  line-height: 1.45;
`

const Content = styled.section`
  display: grid;
  gap: 18px;
`

const TabsRow = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 18px 20px 0;
`

const TabButton = styled.button<{ $active: boolean }>`
  padding: 10px 16px;
  border: 1px solid ${({ $active }) => ($active ? '#2f4f84' : '#d8dfe7')};
  color: ${({ $active }) => ($active ? '#2f4f84' : '#5d6d81')};
  font: inherit;
  font-weight: 700;
  background: ${({ $active }) => ($active ? '#f5f9ff' : '#fff')};
  cursor: pointer;
`

const ResultGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
  padding: 20px;

  @media (max-width: 1320px) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  @media (max-width: 820px) {
    grid-template-columns: 1fr;
  }
`

const ProductCard = styled.article`
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  min-height: 520px;
  border: 1px solid #d9e1ea;
  background: #fff;
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;

  &:hover {
    border-color: #bfd0e2;
    box-shadow: 0 16px 34px rgba(55, 76, 107, 0.1);
    transform: translateY(-2px);
  }
`

const ProductCardTop = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
  padding: 16px 16px 0;
`

const ProductStamp = styled.div`
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid #d7e1ec;
  color: #58708f;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  background: #f8fbfe;
`

const ActionIconButton = styled.button<{ $active?: boolean }>`
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 1px solid ${({ $active }) => ($active ? '#2f4f84' : '#d7dfe8')};
  color: ${({ $active }) => ($active ? '#2f4f84' : '#6280a8')};
  background: ${({ $active }) => ($active ? '#eef4fb' : '#fff')};
  cursor: pointer;

  &:hover {
    background: #f4f8fd;
  }
`

const ProductVisual = styled.button<{ $from: string; $to: string }>`
  position: relative;
  display: grid;
  place-items: center;
  min-height: 230px;
  margin: 10px 16px 0;
  overflow: hidden;
  border: 1px solid #edf2f7;
  color: #3d4f61;
  background:
    radial-gradient(circle at 50% 22%, rgba(255, 255, 255, 0.9), transparent 28%),
    linear-gradient(180deg, ${({ $to }) => $to} 0%, #ffffff 36%, #ffffff 100%);
  cursor: pointer;

  &::before {
    position: absolute;
    inset: 18px 22px auto;
    height: 132px;
    border-radius: 50%;
    background: radial-gradient(circle, ${({ $from }) => $from} 0%, rgba(255, 255, 255, 0) 70%);
    content: '';
    filter: blur(8px);
    opacity: 0.78;
  }
`

const ProductVisualLabel = styled.span`
  position: relative;
  z-index: 1;
  color: rgba(35, 53, 77, 0.72);
  font-size: 46px;
  font-weight: 800;
  letter-spacing: 0.04em;
`

const ProductBody = styled.div`
  display: grid;
  gap: 12px;
  padding: 18px 20px 14px;
`

const ProductTechMeta = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`

const ProductTechLine = styled.div`
  display: grid;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid #e4ebf2;
  background: #fbfcfe;
`

const ProductTechLabel = styled.span`
  color: #7c8a9b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
`

const ProductTechValue = styled.span`
  color: #31455f;
  font-size: 13px;
  line-height: 1.45;
`

const ProductTitle = styled.button`
  padding: 0;
  border: 0;
  color: #2f3b4c;
  font: inherit;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.42;
  text-align: left;
  background: transparent;
  cursor: pointer;
`

const ProductMeta = styled.div`
  display: grid;
  gap: 10px;
  color: #4f5f74;
  font-size: 14px;
  line-height: 1.45;
`

const ProductContextRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`

const ProductContextChip = styled.span<{ $tone?: 'neutral' | 'accent' | 'success' | 'warning' }>`
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

const ProductReasonPanel = styled.div`
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid #dce5ee;
  background: linear-gradient(180deg, #fbfcfe 0%, #ffffff 100%);
`

const ProductReasonHeader = styled.div`
  color: #405672;
  font-size: 12px;
  font-weight: 700;
`

const ProductReasonList = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`

const ProductReasonChip = styled.span`
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-left: 3px solid #2f4f84;
  color: #596a7f;
  font-size: 12px;
  line-height: 1.35;
  background: #f6f9fd;
`

const ProductReasonText = styled.span`
  color: #63758a;
  font-size: 13px;
  line-height: 1.5;
`

const ProductFooter = styled.div`
  display: grid;
  gap: 12px;
  margin-top: auto;
  padding: 0 20px 18px;
`

const ProductStatusRow = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
`

const ProductStatusCard = styled.div`
  display: grid;
  gap: 2px;
  padding-top: 10px;
  border-top: 1px solid #edf1f5;
`

const ProductStatusValue = styled.span`
  color: #2b405f;
  font-size: 15px;
  font-weight: 700;
`

const ProductStatusLabel = styled.span`
  color: #8996a7;
  font-size: 12px;
`

const ProductActions = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

const ExplanationBand = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 0 20px 20px;
`

const ExplanationChip = styled.div`
  padding: 10px 12px;
  border-left: 3px solid #2f4f84;
  background: #f6f9fd;
  color: #556579;
  font-size: 13px;
  line-height: 1.4;
`

const CompareTable = styled.div`
  display: grid;
  gap: 18px;
  padding: 0 20px 20px;
`

const CompareLead = styled.div`
  display: grid;
  gap: 6px;
  padding: 18px 20px;
  border: 1px solid #dbe3ec;
  color: #607085;
  background:
    radial-gradient(circle at top right, rgba(47, 79, 132, 0.08), transparent 28%),
    linear-gradient(180deg, #fbfcfe 0%, #ffffff 100%);
  font-size: 13px;
  line-height: 1.55;
`

const CompareLeadTitle = styled.span`
  color: #30415a;
  font-size: 15px;
  font-weight: 700;
`

const CompareCards = styled.div`
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;

  @media (max-width: 1280px) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  @media (max-width: 720px) {
    grid-template-columns: 1fr;
  }
`

const CompareSubjectCard = styled.section`
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: 12px;
  min-height: 380px;
  padding: 16px;
  border: 1px solid #dbe3ec;
  background: #fff;
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
`

const CompareSubjectTop = styled.div`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
`

const CompareSubjectStamp = styled(ProductStamp)`
  width: fit-content;
`

const CompareSubjectSignalRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
`

const CompareSubjectVisual = styled.div<{ $from: string; $to: string }>`
  display: grid;
  place-items: center;
  min-height: 150px;
  border: 1px solid #edf2f7;
  background:
    radial-gradient(circle at 50% 22%, rgba(255, 255, 255, 0.88), transparent 28%),
    linear-gradient(180deg, ${({ $to }) => $to} 0%, #ffffff 42%, #ffffff 100%);
`

const CompareSubjectTitle = styled.div`
  color: #2f3b4c;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.45;
`

const CompareSubjectMeta = styled.div`
  display: grid;
  gap: 8px;
  color: #66778b;
  font-size: 12px;
  line-height: 1.45;
`

const CompareMetaCard = styled.div`
  display: grid;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid #e4ebf2;
  background: #fbfcfe;
`

const CompareMetaLabel = styled.span`
  color: #7c8a9b;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
`

const CompareMetaValue = styled.span`
  color: #31455f;
  font-size: 13px;
  line-height: 1.45;
`

const CompareSubjectFooter = styled.div`
  display: grid;
  gap: 12px;
  margin-top: auto;
`

const CompareGrid = styled.div`
  display: grid;
  grid-template-columns: 260px repeat(4, minmax(220px, 1fr));
  min-width: 1040px;
  border-top: 1px solid #dde5ee;
  border-left: 1px solid #dde5ee;
`

const CompareCell = styled.div<{ $header?: boolean; $emphasis?: boolean }>`
  min-height: 56px;
  padding: 13px 14px;
  border-right: 1px solid #dde5ee;
  border-bottom: 1px solid #dde5ee;
  color: ${({ $header }) => ($header ? '#30415a' : '#55667b')};
  font-size: 13px;
  font-weight: ${({ $header }) => ($header ? 700 : 400)};
  background: ${({ $header, $emphasis }) =>
    $header
      ? 'linear-gradient(180deg, #f7f9fc 0%, #fdfefe 100%)'
      : $emphasis
      ? '#fff8eb'
      : '#fff'};
`

const CompareCellLabel = styled.div`
  color: #30415a;
  font-size: 13px;
  font-weight: 700;
`

const CompareCellHint = styled.div`
  margin-top: 3px;
  color: #8391a2;
  font-size: 11px;
`

const LoginShell = styled.section`
  display: grid;
  gap: 26px;
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 52px 0;

  @media (max-width: 760px) {
    width: min(100%, calc(100% - 20px));
  }
`

const LoginHero = styled.section`
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 24px;
  padding: 34px;
  border: 1px solid #d8e0e8;
  background:
    radial-gradient(circle at top right, rgba(47, 79, 132, 0.16), transparent 34%),
    linear-gradient(180deg, #ffffff 0%, #f7f9fc 100%);

  @media (max-width: 920px) {
    grid-template-columns: 1fr;
    padding: 24px;
  }
`

const LoginCards = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;

  @media (max-width: 920px) {
    grid-template-columns: 1fr;
  }
`

const LoginCard = styled.button<{ $active: boolean }>`
  display: grid;
  gap: 12px;
  padding: 18px;
  border: 1px solid ${({ $active }) => ($active ? '#2f4f84' : '#d9e0e8')};
  color: #2d3c54;
  font: inherit;
  text-align: left;
  background: ${({ $active }) => ($active ? '#f5f9ff' : '#fff')};
  cursor: pointer;
`

const LoginRole = styled.span<{ $role: string }>`
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 4px 10px;
  color: ${({ $role }) => ($role === 'supplier' ? '#8a4a14' : '#24467a')};
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: ${({ $role }) => ($role === 'supplier' ? '#fff1e4' : '#edf4ff')};
`

const LoginState = styled.span<{ $mode: string }>`
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 4px 10px;
  color: ${({ $mode }) =>
    $mode === 'history' ? '#0f5c38' : $mode === 'context' ? '#24467a' : '#6b4b16'};
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: ${({ $mode }) =>
    $mode === 'history' ? '#e8f7ef' : $mode === 'context' ? '#edf4ff' : '#fff4df'};
`

const LoginHintList = styled.div`
  display: grid;
  gap: 10px;
`

const LoginHint = styled.div`
  padding: 12px 14px;
  border-left: 3px solid #cb3428;
  color: #56687e;
  background: rgba(255, 255, 255, 0.88);
`

const LoginModeSwitch = styled.div`
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  width: fit-content;
  border: 1px solid #d7dee7;
  background: rgba(255, 255, 255, 0.82);
`

const LoginModeButton = styled.button<{ $active: boolean }>`
  border: 0;
  padding: 12px 16px;
  color: ${({ $active }) => ($active ? '#20477f' : '#68788b')};
  font: inherit;
  font-weight: 700;
  background: ${({ $active }) => ($active ? '#eef5ff' : 'transparent')};
  cursor: pointer;
`

const LoginSearchPanel = styled.div`
  display: grid;
  gap: 14px;
`

const LoginSearchMeta = styled.div`
  color: #7d8b9b;
  font-size: 13px;
`

function HomePage() {
  const [session, setSession] = useState<AuthSession | null>(() => readStoredSession())

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    if (!session) {
      clearStoredSession()
      return
    }

    writeStoredSession(session)
  }, [session])

  if (!session) {
    return <LoginScreen onLogin={setSession} />
  }

  return <Workspace session={session} onLogout={() => setSession(null)} />
}

function LoginScreen({ onLogin }: { onLogin: (value: AuthSession) => void }) {
  const [loginMode, setLoginMode] = useState<'demo' | 'inn'>('demo')
  const [selectedUserId, setSelectedUserId] = useState('')
  const [selectedBuyerInn, setSelectedBuyerInn] = useState('')
  const [innQuery, setInnQuery] = useState('')
  const [messageApi, contextHolder] = message.useMessage()
  const deferredInnQuery = useDeferredValue(innQuery)
  const normalizedInnQuery = deferredInnQuery.replace(/\D/g, '')

  const demoUsersQuery = useQuery({
    queryKey: ['demo-users'],
    queryFn: getDemoUsers,
  })

  const customerAccountsQuery = useQuery({
    queryKey: ['customer-accounts', normalizedInnQuery],
    queryFn: () => getCustomerAccounts(normalizedInnQuery),
    enabled: loginMode === 'inn' && normalizedInnQuery.length >= 3,
  })

  const effectiveSelectedUserId = selectedUserId || demoUsersQuery.data?.[0]?.id || ''
  const effectiveSelectedBuyerInn =
    selectedBuyerInn || customerAccountsQuery.data?.[0]?.buyer_inn || normalizedInnQuery || ''

  const demoLoginMutation = useMutation({
    mutationFn: loginDemoUser,
    onSuccess: (data) => {
      onLogin(data)
    },
    onError: (error) => {
      const description = error instanceof Error ? error.message : 'Не удалось выполнить вход'
      void messageApi.error(description)
    },
  })

  const innLoginMutation = useMutation({
    mutationFn: loginCustomerByInn,
    onSuccess: (data) => {
      onLogin(data)
    },
    onError: (error) => {
      const description = error instanceof Error ? error.message : 'Не удалось выполнить вход'
      void messageApi.error(description)
    },
  })

  const isLoginPending = demoLoginMutation.isPending || innLoginMutation.isPending

  function handleLogin() {
    if (loginMode === 'inn') {
      if (!effectiveSelectedBuyerInn) {
        return
      }
      innLoginMutation.mutate(effectiveSelectedBuyerInn)
      return
    }

    if (!effectiveSelectedUserId) {
      return
    }
    demoLoginMutation.mutate(effectiveSelectedUserId)
  }

  const customerCards: CustomerInnAccount[] = customerAccountsQuery.data ?? []

  return (
    <Screen>
      {contextHolder}
      <LoginShell>
        <LoginHero>
          <div style={{ display: 'grid', gap: 18 }}>
            <Brand>
              <BrandLogo src="/portal_logo.png" alt="Портал поставщиков" />
            </Brand>

            <Typography.Title level={1} style={{ margin: 0, color: '#2b3950', fontSize: 42 }}>
              Вход в демо-кабинет закупок
            </Typography.Title>
            <Typography.Paragraph style={{ margin: 0, color: '#607085', fontSize: 18 }}>
              Можно зайти как в готовый demo-кабинет или выбрать реального заказчика по ИНН
              из загруженного `Контракты*.csv`, чтобы посмотреть, как история закупок влияет
              на поиск и рекомендации.
            </Typography.Paragraph>

            <LoginHintList>
              <LoginHint>Заказчик ищет СТЕ, добавляет позиции в избранное, сравнение и корзину.</LoginHint>
              <LoginHint>Поставщик видит тот же каталог и может анализировать конкурентов и спрос.</LoginHint>
              <LoginHint>Поиск учитывает опечатки, синонимы и свежие действия пользователя.</LoginHint>
            </LoginHintList>
          </div>

          <div style={{ display: 'grid', gap: 18 }}>
            <LoginModeSwitch>
              <LoginModeButton
                type="button"
                $active={loginMode === 'demo'}
                onClick={() => setLoginMode('demo')}
              >
                Demo-пользователи
              </LoginModeButton>
              <LoginModeButton
                type="button"
                $active={loginMode === 'inn'}
                onClick={() => setLoginMode('inn')}
              >
                Вход по ИНН
              </LoginModeButton>
            </LoginModeSwitch>

            {loginMode === 'demo' ? (
              demoUsersQuery.isLoading ? (
                <Skeleton active paragraph={{ rows: 6 }} />
              ) : (
                <LoginCards>
                  {(demoUsersQuery.data ?? []).map((user) => {
                    const entryMode = user.entry_mode ?? (user.has_history ? 'history' : 'empty')
                    const entryLabel =
                      entryMode === 'history'
                        ? 'С историей'
                        : entryMode === 'context'
                          ? 'С контекстом'
                          : 'Пустой кабинет'

                    return (
                      <LoginCard
                        key={user.id}
                        type="button"
                        $active={user.id === effectiveSelectedUserId}
                        onClick={() => setSelectedUserId(user.id)}
                      >
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <LoginRole $role={user.role}>
                            {user.role === 'supplier' ? 'Поставщик' : 'Заказчик'}
                          </LoginRole>
                          <LoginState $mode={entryMode}>
                            {entryLabel}
                          </LoginState>
                        </div>
                        <Typography.Title level={4} style={{ margin: 0 }}>
                          {user.name}
                        </Typography.Title>
                        <Typography.Text style={{ color: '#5c6e84' }}>
                          {user.organization_name}
                        </Typography.Text>
                        <Typography.Text style={{ color: '#6f7d8e' }}>
                          {user.persona}
                        </Typography.Text>
                        {user.entry_note ? (
                          <Typography.Text style={{ color: '#8a97a8', fontSize: 13 }}>
                            {user.entry_note}
                          </Typography.Text>
                        ) : null}
                      </LoginCard>
                    )
                  })}
                </LoginCards>
              )
            ) : (
              <LoginSearchPanel>
                <Input
                  size="large"
                  prefix={<SearchOutlined />}
                  placeholder="Введите ИНН заказчика из Контракты*.csv"
                  value={innQuery}
                  onChange={(event) => {
                    setInnQuery(event.target.value)
                    setSelectedBuyerInn('')
                  }}
                />
                {normalizedInnQuery.length < 3 ? (
                  <LoginSearchMeta>
                    Введите минимум 3 цифры ИНН. Список формируется по реально загруженным
                    заказчикам из контрактного CSV.
                  </LoginSearchMeta>
                ) : customerAccountsQuery.isLoading ? (
                  <Skeleton active paragraph={{ rows: 4 }} />
                ) : customerCards.length ? (
                  <LoginCards>
                    {customerCards.map((customer) => (
                      <LoginCard
                        key={customer.user_id}
                        type="button"
                        $active={customer.buyer_inn === effectiveSelectedBuyerInn}
                        onClick={() => setSelectedBuyerInn(customer.buyer_inn)}
                      >
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <LoginRole $role="customer">Заказчик</LoginRole>
                          <LoginState $mode={customer.has_history ? 'history' : 'empty'}>
                            {customer.has_history ? 'С историей' : 'Пустой кабинет'}
                          </LoginState>
                        </div>
                        <Typography.Title level={4} style={{ margin: 0 }}>
                          {customer.organization_name}
                        </Typography.Title>
                        <Typography.Text style={{ color: '#5c6e84' }}>
                          ИНН {customer.buyer_inn}
                        </Typography.Text>
                        <Typography.Text style={{ color: '#6f7d8e' }}>
                          Контрактов в истории: {customer.contracts_count}
                        </Typography.Text>
                        {customer.entry_note ? (
                          <Typography.Text style={{ color: '#8a97a8', fontSize: 13 }}>
                            {customer.entry_note}
                          </Typography.Text>
                        ) : null}
                      </LoginCard>
                    ))}
                  </LoginCards>
                ) : (
                  <Empty description="По этому ИНН заказчик в загруженных контрактах не найден" />
                )}
              </LoginSearchPanel>
            )}

            <Button
              type="primary"
              size="large"
              loading={isLoginPending}
              disabled={loginMode === 'demo' ? !effectiveSelectedUserId : !effectiveSelectedBuyerInn}
              onClick={handleLogin}
            >
              Войти в кабинет
            </Button>
          </div>
        </LoginHero>
      </LoginShell>
    </Screen>
  )
}

function Workspace({
  session,
  onLogout,
}: {
  session: AuthSession
  onLogout: () => void
}) {
  const location = useLocation()
  const navigate = useNavigate()
  const actor = useMemo<ActorContext>(() => ({ userId: session.user_id }), [session.user_id])
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()
  const [searchValue, setSearchValue] = useState(() => readStoredValue(STORAGE_KEYS.search))
  const [selectedCategoryId, setSelectedCategoryId] = useState(() => readStoredValue(STORAGE_KEYS.category))
  const [selectedSupplierId, setSelectedSupplierId] = useState(() => readStoredValue(STORAGE_KEYS.supplier))
  const [selectedOriginValue, setSelectedOriginValue] = useState(() => readStoredValue(STORAGE_KEYS.origin))
  const [domesticOnly, setDomesticOnly] = useState(() => readStoredValue(STORAGE_KEYS.domestic) === 'true')
  const [strictMatch, setStrictMatch] = useState(() => readStoredValue(STORAGE_KEYS.strict) === 'true')
  const [sortMode, setSortMode] = useState<SortMode>(() => {
    const stored = readStoredValue(STORAGE_KEYS.sort)
    return stored === 'title_asc' || stored === 'supplier_asc' ? stored : 'relevance'
  })
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>('all')
  const [searchState, setSearchState] = useState<SearchState>({ kind: 'idle' })
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('catalog')
  const [catalogPage, setCatalogPage] = useState(1)
  const [favoritesPage, setFavoritesPage] = useState(1)
  const deferredSearchValue = useDeferredValue(searchValue)
  const catalogSectionRef = useRef<HTMLElement | null>(null)
  const scrollDepthMarksRef = useRef<Set<number>>(new Set())
  const sessionInteractionRef = useRef<Record<string, boolean>>({})
  const compareViewedSessionsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.localStorage.setItem(STORAGE_KEYS.search, searchValue)
    window.localStorage.setItem(STORAGE_KEYS.category, selectedCategoryId)
    window.localStorage.setItem(STORAGE_KEYS.supplier, selectedSupplierId)
    window.localStorage.setItem(STORAGE_KEYS.origin, selectedOriginValue)
    window.localStorage.setItem(STORAGE_KEYS.domestic, String(domesticOnly))
    window.localStorage.setItem(STORAGE_KEYS.strict, String(strictMatch))
    window.localStorage.setItem(STORAGE_KEYS.sort, sortMode)
  }, [searchValue, selectedCategoryId, selectedSupplierId, selectedOriginValue, domesticOnly, strictMatch, sortMode])

  const categoriesQuery = useQuery<CatalogCategory[]>({
    queryKey: ['catalog-categories'],
    queryFn: getCategories,
  })

  const summaryQuery = useQuery<CatalogSummary>({
    queryKey: ['catalog-summary', session.user_id],
    queryFn: () => getCatalogSummary(actor),
  })

  const suppliersQuery = useQuery<CatalogSupplier[]>({
    queryKey: ['catalog-suppliers'],
    queryFn: getSuppliers,
  })

  const productionOriginsQuery = useQuery<ProductionOriginOption[]>({
    queryKey: ['catalog-production-origins'],
    queryFn: getProductionOrigins,
  })

  const feedQuery = useQuery<CatalogFeedResponse>({
    queryKey: [
      'catalog-feed',
      session.user_id,
      selectedCategoryId,
      selectedSupplierId,
      selectedOriginValue,
      domesticOnly,
      catalogPage,
    ],
    queryFn: () =>
      getCatalogFeed({
        actor,
        limit: CATALOG_PAGE_SIZE,
        offset: (catalogPage - 1) * CATALOG_PAGE_SIZE,
        category_id: selectedCategoryId || undefined,
        supplier_id: selectedSupplierId || undefined,
        origin_value: selectedOriginValue || undefined,
        domestic_only: domesticOnly,
      }),
  })

  const suggestionsQuery = useQuery({
    queryKey: ['search-suggestions', session.user_id, deferredSearchValue.trim()],
    queryFn: () => getSearchSuggestions(deferredSearchValue.trim(), actor),
    enabled: deferredSearchValue.trim().length > 1,
  })

  const historyQuery = useQuery({
    queryKey: ['search-history', session.user_id],
    queryFn: () => getSearchHistory(actor),
  })
  const activityQuery = useQuery({
    queryKey: ['search-activity', session.user_id],
    queryFn: () => getSearchActivity(actor, 12),
  })

  const profileQuery = useQuery<SearchProfileResponse>({
    queryKey: ['search-profile', session.user_id],
    queryFn: () => getSearchProfile(actor),
  })

  const purchaseHistoryQuery = useQuery<PurchaseHistoryItem[]>({
    queryKey: ['purchase-history', session.user_id],
    queryFn: () => getPurchaseHistory(actor),
  })

  const supplierInsightsQuery = useQuery<SupplierInsightsResponse>({
    queryKey: ['supplier-insights', session.user_id],
    queryFn: () => getSupplierInsights(actor),
    enabled: session.role === 'supplier',
  })

  const favoritesQuery = useQuery<FavoriteItem[]>({
    queryKey: ['favorites', session.user_id],
    queryFn: () => getFavorites(actor),
  })

  const comparisonQuery = useQuery<ComparisonItem[]>({
    queryKey: ['comparison-items', session.user_id],
    queryFn: () => getComparisonItems(actor),
  })

  const cartQuery = useQuery<CartItem[]>({
    queryKey: ['cart-items', session.user_id],
    queryFn: () => getCartItems(actor),
  })

  const clearHistoryMutation = useMutation({
    mutationFn: () => clearSearchHistory(actor),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['search-history', session.user_id] }),
        queryClient.invalidateQueries({ queryKey: ['search-activity', session.user_id] }),
        queryClient.invalidateQueries({ queryKey: ['search-profile', session.user_id] }),
      ])
      setActivityFilter('all')
      void messageApi.success('История действий пользователя очищена')
    },
    onError: (error) => {
      void messageApi.error(
        error instanceof Error ? error.message : 'Не удалось очистить историю действий',
      )
    },
  })

  const currentSessionId =
    searchState.kind === 'results' ? searchState.response.meta.session_id : null
  const currentResultItems = useMemo(
    () => (searchState.kind === 'results' ? searchState.response.items : []),
    [searchState],
  )
  const visibleCatalogItems = useMemo(() => {
    const items = [...currentResultItems]
    if (sortMode === 'title_asc') {
      items.sort((left, right) => left.title.localeCompare(right.title, 'ru'))
      return items
    }
    if (sortMode === 'supplier_asc') {
      items.sort((left, right) => left.supplier.localeCompare(right.supplier, 'ru'))
      return items
    }
    return items
  }, [currentResultItems, sortMode])
  const visibleCompareItems = useMemo(
    () => comparisonQuery.data ?? [],
    [comparisonQuery.data],
  )
  const resultCategoryCounts = new Map<string, number>()

  for (const item of currentResultItems) {
    resultCategoryCounts.set(item.category, (resultCategoryCounts.get(item.category) ?? 0) + 1)
  }

  const topResultCategories = [...resultCategoryCounts.entries()]
    .sort((left, right) => right[1] - left[1])
    .slice(0, 5)
  const starterScenarios = useMemo(() => buildStarterScenarios(session), [session])
  const hasProfileSignals = Boolean(
    (profileQuery.data?.top_categories.length ?? 0) ||
      (profileQuery.data?.recent_ste_ids.length ?? 0) ||
      (profileQuery.data?.top_suppliers.length ?? 0) ||
      (profileQuery.data?.popular_queries.length ?? 0) ||
      (profileQuery.data?.active_signals.length ?? 0),
  )
  const hasPurchaseHistory = Boolean((purchaseHistoryQuery.data ?? []).length)
  const hasSearchHistory = Boolean((historyQuery.data?.items ?? []).length)
  const showOnboardingStrip =
    (session.entry_mode === 'empty' || session.entry_mode === 'context') &&
    activeTab === 'catalog' &&
    searchState.kind !== 'results'
  const collectionStarterScenarios = starterScenarios.slice(0, 3)
  const filteredActivityItems = useMemo(
    () =>
      (activityQuery.data?.items ?? []).filter(
        (item) => activityFilter === 'all' || getActivityFilterKey(item.event_type) === activityFilter,
      ),
    [activityFilter, activityQuery.data?.items],
  )
  const entryMode = session.entry_mode ?? (session.has_history ? 'history' : 'empty')
  const entryModeLabel =
    entryMode === 'history' ? 'С историей' : entryMode === 'context' ? 'С контекстом' : 'Пустой кабинет'
  const currentScenarioTitle =
    searchState.kind === 'results'
      ? searchState.response.meta.query
      : historyQuery.data?.items?.[0]?.query ?? starterScenarios[0]?.title ?? 'Новый сценарий'
  const currentScenarioHint =
    searchState.kind === 'results'
      ? 'Сейчас в фокусе активная поисковая выдача.'
      : historyQuery.data?.items?.[0]?.query
      ? 'Можно быстро вернуться к последнему рабочему запросу.'
      : 'Для старта используйте сценарии ниже или выполните первый поиск.'
  const profileSignalCount =
    (profileQuery.data?.active_signals.length ?? 0) +
    (profileQuery.data?.top_categories.length ?? 0) +
    (profileQuery.data?.popular_queries.length ?? 0)

  function scrollToCatalogTop() {
    if (typeof window === 'undefined') {
      return
    }

    const top =
      (catalogSectionRef.current?.getBoundingClientRect().top ?? 0) + window.scrollY - RESULTS_SCROLL_OFFSET
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  }

  function handleCatalogPageChange(page: number) {
    setCatalogPage(page)
    scrollToCatalogTop()
  }

  function handleFavoritesPageChange(page: number) {
    setFavoritesPage(page)
    scrollToCatalogTop()
  }

  function markSessionInteraction(sessionId: string | null) {
    if (!sessionId) {
      return
    }
    sessionInteractionRef.current[sessionId] = true
  }

  useEffect(() => {
    scrollDepthMarksRef.current = new Set()
  }, [currentSessionId])

  useEffect(() => {
    if (!currentSessionId || !currentResultItems.length || activeTab !== 'catalog') {
      return
    }

    const thresholds = [25, 50, 75, 100]

    const handleScroll = () => {
      const doc = document.documentElement
      const body = document.body
      const scrollTop = window.scrollY || doc.scrollTop || body.scrollTop || 0
      const scrollHeight = Math.max(
        doc.scrollHeight,
        body.scrollHeight,
        doc.offsetHeight,
        body.offsetHeight,
      )
      const viewportHeight = window.innerHeight || doc.clientHeight || 0
      const denominator = Math.max(1, scrollHeight - viewportHeight)
      const depth = Math.min(100, Math.round((scrollTop / denominator) * 100))

      for (const threshold of thresholds) {
        if (depth < threshold || scrollDepthMarksRef.current.has(threshold)) {
          continue
        }
        scrollDepthMarksRef.current.add(threshold)
        void createSearchEvent({
          session_id: currentSessionId,
          event_type: 'scroll_depth_changed',
          page_type: 'catalog',
          results_page: 1,
          payload: {
            depth_percent: threshold,
            visible_results: Math.min(
              currentResultItems.length,
              Math.max(1, Math.ceil((threshold / 100) * currentResultItems.length)),
            ),
          },
          actor,
        })
      }
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [activeTab, actor, currentResultItems.length, currentSessionId])

  useEffect(() => {
    if (
      activeTab !== 'compare' ||
      !currentSessionId ||
      !visibleCompareItems.length ||
      compareViewedSessionsRef.current.has(currentSessionId)
    ) {
      return
    }

    compareViewedSessionsRef.current.add(currentSessionId)
    void createSearchEvent({
      session_id: currentSessionId,
      event_type: 'compare_viewed',
      page_type: 'compare',
      payload: {
        compare_count: visibleCompareItems.length,
        ste_ids: visibleCompareItems.map((item) => item.ste_id).join(','),
      },
      actor,
    })
    markSessionInteraction(currentSessionId)
  }, [activeTab, actor, currentSessionId, visibleCompareItems])

  async function runSearch(
    nextQuery?: string,
    eventMeta?: { type: 'suggestion_clicked'; label: string; source: string },
    overrides?: {
      categoryId?: string
      supplierId?: string
      originValue?: string
      domesticOnly?: boolean
      strictMatch?: boolean
    },
  ) {
    const query = (nextQuery ?? searchValue).trim()
    const effectiveCategoryId = (overrides?.categoryId ?? selectedCategoryId) || undefined
    const effectiveSupplierId = (overrides?.supplierId ?? selectedSupplierId) || undefined
    const effectiveOriginValue = (overrides?.originValue ?? selectedOriginValue) || undefined
    const effectiveDomesticOnly = overrides?.domesticOnly ?? domesticOnly
    const effectiveStrictMatch = overrides?.strictMatch ?? strictMatch
    if (!query) {
      setSearchState({ kind: 'idle' })
      setCatalogPage(1)
      return
    }

    const previousResponse =
      searchState.kind === 'results' ? searchState.response : null
    const previousSessionId = previousResponse?.meta.session_id ?? null
    const previousQuery = previousResponse?.meta.query.trim() ?? ''

    if (previousSessionId && previousQuery && previousQuery !== query) {
      void createSearchEvent({
        session_id: previousSessionId,
        event_type: 'search_refined',
        query_text: previousQuery,
        normalized_query: previousResponse?.meta.normalized_query,
        corrected_query: previousResponse?.meta.corrected_query,
        page_type: 'catalog',
        payload: { next_query: query },
        actor,
      })

      if (!sessionInteractionRef.current[previousSessionId]) {
        void createSearchEvent({
          session_id: previousSessionId,
          event_type: 'search_abandoned',
          query_text: previousQuery,
          normalized_query: previousResponse?.meta.normalized_query,
          corrected_query: previousResponse?.meta.corrected_query,
          page_type: 'catalog',
          payload: { next_query: query },
          actor,
        })
      }
    }

    setSearchState({ kind: 'loading' })

    try {
      const response = await searchCatalog({
        query,
        filters: {
          strict_match: effectiveStrictMatch,
          category_id: effectiveCategoryId,
          supplier_id: effectiveSupplierId,
          origin_value: effectiveOriginValue,
          domestic_only: effectiveDomesticOnly,
        },
        actor,
      })
      writeLastSearchSessionId(response.meta.session_id)
      setSearchState({ kind: 'results', response })
      setActiveTab('catalog')
      setCatalogPage(1)

      if (eventMeta) {
        void createSearchEvent({
          session_id: response.meta.session_id,
          event_type: eventMeta.type,
          query_text: response.meta.query,
          normalized_query: response.meta.normalized_query,
          corrected_query: response.meta.corrected_query,
          page_type: 'catalog',
          payload: {
            label: eventMeta.label,
            source: eventMeta.source,
          },
          actor,
        })
      }

      void createSearchEvent({
        session_id: response.meta.session_id,
        event_type: 'search_results_rendered',
        query_text: response.meta.query,
        normalized_query: response.meta.normalized_query,
        corrected_query: response.meta.corrected_query,
        page_type: 'catalog',
        results_page: 1,
        payload: {
          results_count: response.items.length,
          category_id: effectiveCategoryId || '',
          supplier_id: effectiveSupplierId || '',
          origin_value: effectiveOriginValue || '',
          domestic_only: effectiveDomesticOnly,
          strict_match: effectiveStrictMatch,
          top_ste_ids: response.items.slice(0, 10).map((item) => item.id).join(','),
        },
        actor,
      })

      if (response.items.length) {
        void createSearchImpressions({
          items: response.items.slice(0, 12).map((item, index) => ({
            search_session_id: response.meta.session_id,
            ste_id: item.id,
            rank_position: index + 1,
            results_page: 1,
            visible: true,
          })),
          actor,
        })
      }
    } catch (error) {
      setSearchState({
        kind: 'error',
        message: error instanceof Error ? error.message : 'Не удалось выполнить поиск',
      })
    }
  }

  async function applyStarterScenario(scenario: StarterScenario) {
    setSearchValue(scenario.query)
    setSelectedCategoryId(scenario.categoryId ?? '')
    setSelectedSupplierId('')
    setSelectedOriginValue('')
    setDomesticOnly(false)
    setStrictMatch(Boolean(scenario.strictMatch))
    setActiveTab('catalog')
    setCatalogPage(1)
    await runSearch(scenario.query, undefined, {
      categoryId: scenario.categoryId,
      supplierId: undefined,
      originValue: undefined,
      domesticOnly: false,
      strictMatch: scenario.strictMatch,
    })
  }

  useEffect(() => {
    const starterScenario = (
      location.state as { starterScenario?: StarterScenario } | null
    )?.starterScenario
    if (!starterScenario) {
      return
    }

    void applyStarterScenario(starterScenario).finally(() => {
      navigate(location.pathname, { replace: true, state: null })
    })
  }, [location.pathname, location.state, navigate])

  function openCollectionStarterScenario(scenario: StarterScenario) {
    setActiveTab('catalog')
    setFavoritesPage(1)
    scrollToCatalogTop()
    void applyStarterScenario(scenario)
  }

  function openActivitySearch(query: string) {
    setActiveTab('catalog')
    setCatalogPage(1)
    setSearchValue(query)
    scrollToCatalogTop()
    void runSearch(query)
  }

  function openActivityProduct(steId: string) {
    navigate(buildProductPath(steId, currentSessionId))
  }

  async function invalidateUserSignals() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['search-profile', session.user_id] }),
      queryClient.invalidateQueries({ queryKey: ['favorites', session.user_id] }),
      queryClient.invalidateQueries({ queryKey: ['comparison-items', session.user_id] }),
      queryClient.invalidateQueries({ queryKey: ['cart-items', session.user_id] }),
      queryClient.invalidateQueries({ queryKey: ['catalog-summary', session.user_id] }),
    ])
  }

  async function rerunSearchIfNeeded() {
    if (searchState.kind === 'results' && searchState.response.meta.query.trim()) {
      await runSearch(searchState.response.meta.query)
    }
  }

  function handleCategoryChange(value?: string) {
    const nextValue = value ?? ''
    if (currentSessionId && selectedCategoryId && selectedCategoryId !== nextValue) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: 'filter_removed',
        page_type: 'catalog',
        payload: { filter_name: 'category_id', filter_value: selectedCategoryId },
        actor,
      })
    }
    if (currentSessionId && nextValue && nextValue !== selectedCategoryId) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: 'filter_applied',
        page_type: 'catalog',
        payload: { filter_name: 'category_id', filter_value: nextValue },
        actor,
      })
    }
    setSelectedCategoryId(nextValue)
    setCatalogPage(1)
  }

  function handleSupplierChange(value?: string) {
    const nextValue = value ?? ''
    if (currentSessionId && selectedSupplierId && selectedSupplierId !== nextValue) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: 'filter_removed',
        page_type: 'catalog',
        payload: { filter_name: 'supplier_id', filter_value: selectedSupplierId },
        actor,
      })
    }
    if (currentSessionId && nextValue && nextValue !== selectedSupplierId) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: 'filter_applied',
        page_type: 'catalog',
        payload: { filter_name: 'supplier_id', filter_value: nextValue },
        actor,
      })
    }
    setSelectedSupplierId(nextValue)
    setCatalogPage(1)
  }

  function handleOriginChange(value?: string) {
    const nextValue = value ?? ''
    if (currentSessionId && selectedOriginValue && selectedOriginValue !== nextValue) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: 'filter_removed',
        page_type: 'catalog',
        payload: { filter_name: 'origin_value', filter_value: selectedOriginValue },
        actor,
      })
    }
    if (currentSessionId && nextValue && nextValue !== selectedOriginValue) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: 'filter_applied',
        page_type: 'catalog',
        payload: { filter_name: 'origin_value', filter_value: nextValue },
        actor,
      })
    }
    setSelectedOriginValue(nextValue)
    setCatalogPage(1)
  }

  function toggleDomesticOnly() {
    const nextValue = !domesticOnly
    if (currentSessionId) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: nextValue ? 'filter_applied' : 'filter_removed',
        page_type: 'catalog',
        payload: { filter_name: 'domestic_only', filter_value: nextValue },
        actor,
      })
    }
    setDomesticOnly(nextValue)
    setCatalogPage(1)
  }

  function toggleStrictMatch() {
    const nextValue = !strictMatch
    if (currentSessionId) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: nextValue ? 'filter_applied' : 'filter_removed',
        page_type: 'catalog',
        payload: { filter_name: 'strict_match', filter_value: nextValue },
        actor,
      })
    }
    setStrictMatch(nextValue)
    setCatalogPage(1)
  }

  function handleSortChange(value: SortMode) {
    if (value === sortMode) {
      return
    }
    if (currentSessionId) {
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: 'sort_changed',
        page_type: 'catalog',
        payload: { previous_sort: sortMode, next_sort: value },
        actor,
      })
      markSessionInteraction(currentSessionId)
    }
    setSortMode(value)
    setCatalogPage(1)
  }

  const favoriteIds = new Set((favoritesQuery.data ?? []).map((item) => item.ste_id))
  const comparisonIds = new Set((comparisonQuery.data ?? []).map((item) => item.ste_id))
  const cartMap = new Map((cartQuery.data ?? []).map((item) => [item.ste_id, item.quantity]))

  const favoriteMutation = useMutation({
    mutationFn: async ({ steId, active }: { steId: string; active: boolean }) => {
      if (active) {
        await removeFavorite(steId, actor)
        return
      }
      await addFavorite(steId, actor)
    },
    onSuccess: async (_data, variables) => {
      await invalidateUserSignals()
      if (currentSessionId) {
        markSessionInteraction(currentSessionId)
        await createSearchEvent({
          session_id: currentSessionId,
          event_type: variables.active ? 'favorite_removed' : 'favorite_added',
          ste_id: variables.steId,
          actor,
        })
      }
      await rerunSearchIfNeeded()
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось обновить избранное')
    },
  })

  const comparisonMutation = useMutation({
    mutationFn: async ({ steId, active }: { steId: string; active: boolean }) => {
      if (active) {
        await removeComparisonItem(steId, actor)
        return
      }
      await addComparisonItem(steId, actor)
    },
    onSuccess: async (_data, variables) => {
      await invalidateUserSignals()
      if (currentSessionId) {
        markSessionInteraction(currentSessionId)
        await createSearchEvent({
          session_id: currentSessionId,
          event_type: variables.active ? 'comparison_removed' : 'comparison_added',
          ste_id: variables.steId,
          actor,
        })
      }
      await rerunSearchIfNeeded()
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось обновить сравнение')
    },
  })

  const cartMutation = useMutation({
    mutationFn: async ({ steId, quantity }: { steId: string; quantity: number }) => {
      await addCartItem(steId, quantity, actor)
    },
    onSuccess: async (_data, variables) => {
      await invalidateUserSignals()
      if (currentSessionId) {
        markSessionInteraction(currentSessionId)
        await createSearchEvent({
          session_id: currentSessionId,
          event_type: 'cart_added',
          ste_id: variables.steId,
          payload: { quantity: variables.quantity },
          actor,
        })
      }
      await rerunSearchIfNeeded()
    },
    onError: (error) => {
      void messageApi.error(error instanceof Error ? error.message : 'Не удалось обновить корзину')
    },
  })

  const compareAttributeKeys = Array.from(
    new Set(
      visibleCompareItems.flatMap((item) => Object.keys(item.item.attributes)).filter(Boolean),
    ),
  )
  const compareRowLabels = ['Категория', 'Поставщик', 'Статус', ...compareAttributeKeys]
  const compareDifferenceLabels = new Set(
    compareRowLabels.filter((label) => {
      const values = visibleCompareItems.map((item) =>
        label === 'Категория'
          ? item.item.category_name
          : label === 'Поставщик'
          ? item.item.supplier_name
          : label === 'Статус'
          ? item.item.status
          : item.item.attributes[label] ?? '—',
      )
      return new Set(values).size > 1
    }),
  )

  const activeCollectionItems =
    activeTab === 'favorites'
      ? favoritesQuery.data?.map((item) => item.item) ?? []
      : activeTab === 'compare'
      ? comparisonQuery.data?.map((item) => item.item) ?? []
      : []
  const favoriteMaxPage = Math.max(1, Math.ceil(activeCollectionItems.length / FAVORITES_PAGE_SIZE))
  const effectiveFavoritesPage = Math.min(favoritesPage, favoriteMaxPage)
  const pagedFavoriteItems = activeCollectionItems.slice(
    (effectiveFavoritesPage - 1) * FAVORITES_PAGE_SIZE,
    effectiveFavoritesPage * FAVORITES_PAGE_SIZE,
  )

  function renderProductCard(
    item: {
      id: string
      title: string
      supplier: string
      category: string
      score?: number
      reasons?: string[]
      statusLabel?: string
      secondaryLabel?: string
    },
    options?: {
      trackResultClick?: boolean
      showReasons?: boolean
      rankPosition?: number
    },
  ) {
    const [from, to] = buildCardTone(item.id)
    const inFavorites = favoriteIds.has(item.id)
    const inComparison = comparisonIds.has(item.id)
    const inCart = cartMap.has(item.id)
    const statusLabel = item.statusLabel ?? (inCart ? 'В подборке' : 'В каталоге')
    const secondaryLabel = item.secondaryLabel ?? (inComparison ? 'В сравнении' : 'Без предложений')
    const reasonItems = options?.showReasons
      ? (item.reasons ?? []).slice(0, 3).map((reason) => formatSearchReason(reason))
      : []

    const productPath = buildProductPath(item.id, currentSessionId)

    const openInNewTab = () => {
      if (options?.trackResultClick && currentSessionId) {
        markSessionInteraction(currentSessionId)
        void createSearchEvent({
          session_id: currentSessionId,
          event_type: 'result_opened_new_tab',
          ste_id: item.id,
          page_type: 'catalog',
          rank_position: options.rankPosition,
          results_page: 1,
          payload: item.score === undefined ? {} : { score: item.score },
          actor,
        })
      }
      if (typeof window !== 'undefined') {
        window.open(productPath, '_blank', 'noopener,noreferrer')
      }
    }

    const openDetails = () => {
      if (options?.trackResultClick && currentSessionId) {
        markSessionInteraction(currentSessionId)
        void createSearchEvent({
          session_id: currentSessionId,
          event_type: 'result_clicked',
          ste_id: item.id,
          page_type: 'catalog',
          rank_position: options.rankPosition,
          results_page: 1,
          payload: item.score === undefined ? {} : { score: item.score },
          actor,
        }).then(() =>
          queryClient.invalidateQueries({
            queryKey: ['search-profile', session.user_id],
          }),
        )
      }
      navigate(productPath)
    }

    const markIrrelevant = () => {
      if (!currentSessionId) {
        void messageApi.info('Негативный сигнал доступен после поисковой выдачи.')
        return
      }
      markSessionInteraction(currentSessionId)
      void createSearchEvent({
        session_id: currentSessionId,
        event_type: 'irrelevant_marked',
        ste_id: item.id,
        page_type: options?.trackResultClick ? 'catalog' : activeTab,
        rank_position: options?.rankPosition,
        results_page: 1,
        payload: { source_tab: activeTab },
        actor,
      })
      void messageApi.success('Позиция отмечена как нерелевантная.')
    }

    return (
      <ProductCard key={item.id}>
        <ProductCardTop>
          <ProductStamp>ID СТЕ {item.id}</ProductStamp>
          <ProductActions>
            <ActionIconButton
              type="button"
              $active={inFavorites}
              onClick={() =>
                favoriteMutation.mutate({
                  steId: item.id,
                  active: inFavorites,
                })
              }
            >
              {inFavorites ? <HeartFilled /> : <HeartOutlined />}
            </ActionIconButton>
            <ActionIconButton
              type="button"
              $active={inComparison}
              onClick={() =>
                comparisonMutation.mutate({
                  steId: item.id,
                  active: inComparison,
                })
              }
            >
              <SwapOutlined />
            </ActionIconButton>
          </ProductActions>
        </ProductCardTop>

        <ProductVisual
          type="button"
          $from={from}
          $to={to}
          onClick={openDetails}
          onAuxClick={(event) => {
            if (event.button === 1) {
              event.preventDefault()
              openInNewTab()
            }
          }}
        >
          <ProductVisualLabel>{buildCardLabel(item.title)}</ProductVisualLabel>
        </ProductVisual>

        <ProductBody>
          <ProductTitle
            type="button"
            onClick={openDetails}
            onAuxClick={(event) => {
              if (event.button === 1) {
                event.preventDefault()
                openInNewTab()
              }
            }}
          >
            {item.title}
          </ProductTitle>
          <ProductContextRow>
            <ProductContextChip $tone="neutral">ID {item.id}</ProductContextChip>
            {inFavorites ? <ProductContextChip $tone="accent">Избранное</ProductContextChip> : null}
            {inComparison ? <ProductContextChip $tone="warning">Сравнение</ProductContextChip> : null}
            {inCart ? <ProductContextChip $tone="success">В корзине</ProductContextChip> : null}
            {typeof item.score === 'number' ? (
              <ProductContextChip $tone="accent">Score {item.score.toFixed(2)}</ProductContextChip>
            ) : null}
          </ProductContextRow>
          <ProductTechMeta>
            <ProductTechLine>
              <ProductTechLabel>Поставщик</ProductTechLabel>
              <ProductTechValue>{item.supplier}</ProductTechValue>
            </ProductTechLine>
            <ProductTechLine>
              <ProductTechLabel>Категория</ProductTechLabel>
              <ProductTechValue>{item.category}</ProductTechValue>
            </ProductTechLine>
          </ProductTechMeta>
          <ProductMeta>
            {reasonItems.length ? (
              <ProductReasonPanel>
                <ProductReasonHeader>Почему позиция в фокусе</ProductReasonHeader>
                <ProductReasonList>
                  {reasonItems.map((reason) => (
                    <ProductReasonChip key={`${item.id}-${reason}`}>{reason}</ProductReasonChip>
                  ))}
                </ProductReasonList>
              </ProductReasonPanel>
            ) : null}
            <ProductReasonPanel>
              <ProductReasonHeader>Контекст</ProductReasonHeader>
              <ProductReasonText>
                {reasonItems.length
                  ? 'Карточка уже содержит сигналы для shortlist, сравнения и закупочной подборки.'
                  : 'Позиция доступна для сравнения, сохранения в shortlist и добавления в закупочную корзину.'}
              </ProductReasonText>
            </ProductReasonPanel>
          </ProductMeta>
        </ProductBody>

        <ProductFooter>
          <ProductStatusRow>
            <ProductStatusCard>
              <ProductStatusValue>{statusLabel}</ProductStatusValue>
              <ProductStatusLabel>Состояние позиции</ProductStatusLabel>
            </ProductStatusCard>
            <ProductStatusCard>
              <ProductStatusValue>{secondaryLabel}</ProductStatusValue>
              <ProductStatusLabel>Рабочий контекст</ProductStatusLabel>
            </ProductStatusCard>
          </ProductStatusRow>
          <ProductActions>
            <SurfaceButton
              $tone={inCart ? 'success' : 'accent'}
              $emphasis={inCart ? 'soft' : 'solid'}
              icon={<ShoppingCartOutlined />}
              onClick={() =>
                cartMutation.mutate({
                  steId: item.id,
                  quantity: 1,
                })
              }
            >
              {inCart ? 'В корзине' : 'В корзину'}
            </SurfaceButton>
            <SurfaceButton $tone="danger" $emphasis="soft" onClick={markIrrelevant}>
              Нерелевантно
            </SurfaceButton>
            <SurfaceButton $tone="neutral" $emphasis="soft" onClick={openDetails}>Карточка</SurfaceButton>
          </ProductActions>
        </ProductFooter>
      </ProductCard>
    )
  }

  return (
    <PortalShell
      session={session}
      activeNav="catalog"
      onLogout={onLogout}
      headerTools={
        <HeaderTools>
          <HeaderTool type="button" aria-label="cart" onClick={() => navigate('/cart')}>
            <Badge count={cartQuery.data?.length ?? 0} size="small">
              <ShoppingCartOutlined />
            </Badge>
          </HeaderTool>
        </HeaderTools>
      }
    >
      {contextHolder}
      <Main>
        <SearchStrip>
          <SearchHeroTop>
            <HeroIntroBlock>
              <HeroEyebrow>
                {session.role === 'supplier' ? 'Рабочая зона поставщика' : 'Рабочая зона заказчика'}
              </HeroEyebrow>
              <HeroTitle>
                {session.role === 'supplier'
                  ? 'Следите за спросом, конкурентами и shortlist в одном контуре'
                  : 'Собирайте закупочный сценарий и рабочий shortlist без лишних переходов'}
              </HeroTitle>
              <HeroText>
                {entryMode === 'history'
                  ? 'Кабинет уже накопил историю и сигналы. Верхний блок теперь показывает, в каком режиме вы работаете и какой сценарий сейчас в фокусе.'
                  : entryMode === 'context'
                  ? 'Организационный контекст уже доступен. Используйте его как опору для первого личного сценария и быстрых действий по каталогу.'
                  : 'Новый кабинет стартует с нуля. Сначала выберите предметный сценарий, затем закрепите полезные позиции в избранном, сравнении или корзине.'}
              </HeroText>
              <HeroActionRow>
                {historyQuery.data?.items?.[0]?.query ? (
                  <SurfaceButton $tone="neutral" $emphasis="soft" onClick={() => openActivitySearch(historyQuery.data.items[0].query)}>
                    Последний запрос
                  </SurfaceButton>
                ) : null}
                {session.role === 'supplier' ? (
                  <SurfaceButton $tone="accent" $emphasis="soft" onClick={() => navigate('/supplier')}>
                    Открыть dashboard
                  </SurfaceButton>
                ) : (
                  <SurfaceButton $tone="accent" $emphasis="soft" onClick={() => setActiveTab('favorites')}>
                    Открыть shortlist
                  </SurfaceButton>
                )}
              </HeroActionRow>
            </HeroIntroBlock>

            <SnapshotGrid>
              <SnapshotCard $tone="cool">
                <SnapshotLabel>Режим</SnapshotLabel>
                <SnapshotValue>{entryModeLabel}</SnapshotValue>
                <SnapshotHint>{session.persona ?? 'Рабочий профиль пользователя'}</SnapshotHint>
              </SnapshotCard>
              <SnapshotCard $tone="cool">
                <SnapshotLabel>Текущий сценарий</SnapshotLabel>
                <SnapshotValue>{currentScenarioTitle}</SnapshotValue>
                <SnapshotHint>{currentScenarioHint}</SnapshotHint>
              </SnapshotCard>
              <SnapshotCard $tone="cool">
                <SnapshotLabel>Сигналы профиля</SnapshotLabel>
                <SnapshotValue>{profileSignalCount.toLocaleString('ru-RU')}</SnapshotValue>
                <SnapshotHint>
                  {hasProfileSignals
                    ? 'Профиль уже влияет на explainability и приоритизацию.'
                    : 'Сигналы появятся после первых поисков и действий в каталоге.'}
                </SnapshotHint>
              </SnapshotCard>
              <SnapshotCard $tone="cool">
                <SnapshotLabel>Рабочий контур</SnapshotLabel>
                <SnapshotValue>
                  {(favoritesQuery.data?.length ?? 0) + (cartQuery.data?.length ?? 0)}
                </SnapshotValue>
                <SnapshotHint>
                  Позиции в избранном и корзине, к которым можно быстро вернуться.
                </SnapshotHint>
              </SnapshotCard>
            </SnapshotGrid>
          </SearchHeroTop>

          <SearchRow>
            <CatalogButton icon={<AppstoreOutlined />}>Каталог</CatalogButton>

            <SearchInputWrap>
              <SearchAutocomplete
                options={buildAutocompleteOptions(suggestionsQuery.data?.items ?? [])}
                value={searchValue}
                placement="bottomLeft"
                getPopupContainer={(triggerNode) => triggerNode.parentElement ?? document.body}
                onChange={(value) => setSearchValue(String(value))}
                onSelect={(value) => {
                  const selectedValue = String(value)
                  const matchedSuggestion = suggestionsQuery.data?.items.find(
                    (item) => item.label === selectedValue,
                  )
                  setSearchValue(selectedValue)
                  void runSearch(
                    selectedValue,
                    matchedSuggestion
                      ? {
                          type: 'suggestion_clicked',
                          label: matchedSuggestion.label,
                          source: `${matchedSuggestion.group}:${matchedSuggestion.type}`,
                        }
                      : undefined,
                  )
                }}
                popupClassName="search-suggestions-popup"
              >
                <SearchField
                  placeholder="Введите название категории, товара или ID СТЕ"
                  onPressEnter={() => void runSearch()}
                />
              </SearchAutocomplete>
              <SearchSubmit
                type="primary"
                icon={<SearchOutlined />}
                onClick={() => void runSearch()}
              />
            </SearchInputWrap>

            <SurfaceButton
              $tone="neutral"
              $emphasis="soft"
              icon={<StarOutlined />}
              onClick={() => {
                setActiveTab('favorites')
                setFavoritesPage(1)
              }}
            >
              Есть предложения
            </SurfaceButton>
          </SearchRow>

          <SearchMetaRow>
            <SearchMetaGroup>
              <StatusPill $tone={session.role === 'supplier' ? 'supplier' : 'info'}>
                {session.role === 'supplier' ? 'Поставщик' : 'Заказчик'}
              </StatusPill>
              <StatusPill $tone="neutral">{session.persona}</StatusPill>
              <StatusPill $tone={strictMatch ? 'danger' : 'neutral'}>
                {strictMatch ? 'Strict match' : 'Мягкий поиск'}
              </StatusPill>
            </SearchMetaGroup>

            <SearchMetaGroup>
              <SurfaceButton
                $tone={strictMatch ? 'accent' : 'neutral'}
                $emphasis={strictMatch ? 'soft' : 'outline'}
                onClick={toggleStrictMatch}
              >
                {strictMatch ? 'Строгое совпадение' : 'Включить strict match'}
              </SurfaceButton>
            </SearchMetaGroup>
          </SearchMetaRow>
        </SearchStrip>

        {showOnboardingStrip ? (
          <OnboardingSurface $tone="cool">
            <OnboardingHeader>
              <OnboardingTitle>
                {session.role === 'supplier'
                  ? 'Быстрый старт для кабинета поставщика'
                  : 'Быстрый старт для нового кабинета'}
              </OnboardingTitle>
              <OnboardingText>
                {session.entry_mode === 'context'
                  ? 'Личный профиль еще пустой, но организационный контекст уже доступен. Начните с готового сценария и соберите первые сигналы в избранном, сравнении и корзине.'
                  : 'История закупок и персональные сигналы пока не собраны. Запустите один из готовых сценариев, чтобы быстро наполнить кабинет полезным контекстом.'}
              </OnboardingText>
              {session.entry_note ? <OnboardingText>{session.entry_note}</OnboardingText> : null}
            </OnboardingHeader>

            <OnboardingGrid>
              {starterScenarios.map((scenario) => (
                <OnboardingCard
                  $tone="cool"
                  key={scenario.key}
                  type="button"
                  onClick={() => void applyStarterScenario(scenario)}
                >
                  <StatusPill $tone="info">Стартовый сценарий</StatusPill>
                  <OnboardingCardTitle $tone="cool">{scenario.title}</OnboardingCardTitle>
                  <OnboardingCardText>{scenario.description}</OnboardingCardText>
                  <OnboardingCardAction $tone="cool">Открыть выдачу</OnboardingCardAction>
                </OnboardingCard>
              ))}
            </OnboardingGrid>
          </OnboardingSurface>
        ) : null}

        <WorkspaceGrid>
          <Sidebar>
            <SidebarCard>
              <SidebarHeader>
                <SidebarTitle level={3}>Фильтры</SidebarTitle>
                <SidebarSubtitle>
                  {searchState.kind === 'results' ? `Найдено ${searchState.response.items.length}` : 'Каталог СТЕ'}
                </SidebarSubtitle>
              </SidebarHeader>

              <FilterStack>
                <FilterMetaCard>
                  Текущий режим: {session.role === 'supplier' ? 'анализ конкурентов' : 'подбор закупки'}.
                  Фильтры работают поверх каталога СТЕ и не меняют профиль пользователя. Фильтр происхождения
                  использует реальные атрибуты карточки товара.
                </FilterMetaCard>
                <FilterField>
                  <FilterLabel>Категория</FilterLabel>
                  <Select
                    size="large"
                    placeholder="Выберите категорию"
                    value={selectedCategoryId || undefined}
                    options={(categoriesQuery.data ?? []).map((item) => ({
                      value: item.id,
                      label: item.name,
                    }))}
                    onChange={(value) => handleCategoryChange(value)}
                    allowClear
                  />
                </FilterField>
                <FilterField>
                  <FilterLabel>Поставщик</FilterLabel>
                  <Select
                    size="large"
                    placeholder="Выберите поставщика"
                    value={selectedSupplierId || undefined}
                    options={(suppliersQuery.data ?? []).map((item) => ({
                      value: item.id,
                      label: item.name,
                    }))}
                    onChange={(value) => handleSupplierChange(value)}
                    allowClear
                    showSearch
                    optionFilterProp="label"
                  />
                </FilterField>
                <FilterField>
                  <FilterLabel>Происхождение</FilterLabel>
                  <Select
                    size="large"
                    placeholder="Страна / регион происхождения"
                    value={selectedOriginValue || undefined}
                    options={(productionOriginsQuery.data ?? []).map((item) => ({
                      value: item.value,
                      label: `${item.label} (${item.item_count.toLocaleString('ru-RU')})`,
                    }))}
                    onChange={(value) => handleOriginChange(value)}
                    allowClear
                    showSearch
                    optionFilterProp="label"
                  />
                </FilterField>
                <FilterField>
                  <FilterLabel>Локализация</FilterLabel>
                  <Button type={domesticOnly ? 'primary' : 'default'} onClick={toggleDomesticOnly}>
                    {domesticOnly ? 'Только отечественные товары' : 'Показать только отечественные'}
                  </Button>
                </FilterField>
                <FilterField>
                  <FilterLabel>Точность поиска</FilterLabel>
                  <Button type={strictMatch ? 'primary' : 'default'} onClick={toggleStrictMatch}>
                    {strictMatch ? 'Строгое совпадение включено' : 'Переключить strict match'}
                  </Button>
                </FilterField>
                <Button type="default" onClick={() => {
                  if (currentSessionId) {
                    if (selectedCategoryId) {
                      void createSearchEvent({
                        session_id: currentSessionId,
                        event_type: 'filter_removed',
                        page_type: 'catalog',
                        payload: { filter_name: 'category_id', filter_value: selectedCategoryId },
                        actor,
                      })
                    }
                    if (selectedSupplierId) {
                      void createSearchEvent({
                        session_id: currentSessionId,
                        event_type: 'filter_removed',
                        page_type: 'catalog',
                        payload: { filter_name: 'supplier_id', filter_value: selectedSupplierId },
                        actor,
                      })
                    }
                    if (selectedOriginValue) {
                      void createSearchEvent({
                        session_id: currentSessionId,
                        event_type: 'filter_removed',
                        page_type: 'catalog',
                        payload: { filter_name: 'origin_value', filter_value: selectedOriginValue },
                        actor,
                      })
                    }
                    if (domesticOnly) {
                      void createSearchEvent({
                        session_id: currentSessionId,
                        event_type: 'filter_removed',
                        page_type: 'catalog',
                        payload: { filter_name: 'domestic_only', filter_value: true },
                        actor,
                      })
                    }
                    if (strictMatch) {
                      void createSearchEvent({
                        session_id: currentSessionId,
                        event_type: 'filter_removed',
                        page_type: 'catalog',
                        payload: { filter_name: 'strict_match', filter_value: true },
                        actor,
                      })
                    }
                    void createSearchEvent({
                      session_id: currentSessionId,
                      event_type: 'filters_cleared',
                      page_type: 'catalog',
                      payload: {
                        category_id: selectedCategoryId || '',
                        supplier_id: selectedSupplierId || '',
                        origin_value: selectedOriginValue || '',
                        domestic_only: domesticOnly,
                        strict_match: strictMatch,
                      },
                      actor,
                    })
                  }
                  setSelectedCategoryId('')
                  setSelectedSupplierId('')
                  setSelectedOriginValue('')
                  setDomesticOnly(false)
                  setStrictMatch(false)
                  setCatalogPage(1)
                }}>
                  Сбросить фильтры
                </Button>
              </FilterStack>
            </SidebarCard>

            <SidebarCard>
              <SidebarHeader>
                <SidebarTitle level={3}>Сводка каталога</SidebarTitle>
                <SidebarSubtitle>Что реально загружено в БД</SidebarSubtitle>
              </SidebarHeader>
              {summaryQuery.isLoading ? (
                <Skeleton active paragraph={{ rows: 4 }} />
              ) : summaryQuery.data ? (
                <>
                  <MetricGrid $columns={2}>
                    <MetricCard>
                      <MetricValue>{summaryQuery.data.ste_items_count.toLocaleString('ru-RU')}</MetricValue>
                      <MetricLabel>Позиций СТЕ</MetricLabel>
                    </MetricCard>
                    <MetricCard>
                      <MetricValue>{summaryQuery.data.categories_count.toLocaleString('ru-RU')}</MetricValue>
                      <MetricLabel>Категорий</MetricLabel>
                    </MetricCard>
                    <MetricCard>
                      <MetricValue>{summaryQuery.data.suppliers_count.toLocaleString('ru-RU')}</MetricValue>
                      <MetricLabel>Поставщиков</MetricLabel>
                    </MetricCard>
                    <MetricCard>
                      <MetricValue>{summaryQuery.data.purchase_history_count.toLocaleString('ru-RU')}</MetricValue>
                      <MetricLabel>Записей истории закупок</MetricLabel>
                    </MetricCard>
                    <MetricCard>
                      <MetricValue>{summaryQuery.data.favorites_count.toLocaleString('ru-RU')}</MetricValue>
                      <MetricLabel>Избранное пользователя</MetricLabel>
                    </MetricCard>
                    <MetricCard>
                      <MetricValue>{summaryQuery.data.cart_count.toLocaleString('ru-RU')}</MetricValue>
                      <MetricLabel>Позиций в корзине</MetricLabel>
                    </MetricCard>
                  </MetricGrid>

                  <SignalList>
                    <SignalCard>
                      Последнее обновление каталога: {formatDateTime(summaryQuery.data.latest_item_updated_at)}
                    </SignalCard>
                  </SignalList>

                  <PurchaseList>
                    {summaryQuery.data.top_categories.map((item) => (
                      <PurchaseCard key={item.id}>
                        <PurchaseTitle>{item.name}</PurchaseTitle>
                        <PurchaseMeta>{item.item_count.toLocaleString('ru-RU')} позиций в каталоге</PurchaseMeta>
                      </PurchaseCard>
                    ))}
                  </PurchaseList>
                </>
              ) : (
                <SignalCard>Сводка пока недоступна.</SignalCard>
              )}
            </SidebarCard>

            <SidebarCard>
              <SidebarHeader>
                <SidebarTitle level={3}>Почему выдача меняется</SidebarTitle>
              </SidebarHeader>
              {profileQuery.isLoading ? (
                <Skeleton active paragraph={{ rows: 4 }} />
              ) : (
                <SignalList>
                  {(profileQuery.data?.active_signals ?? []).length ? (
                    profileQuery.data?.active_signals.map((item) => (
                      <SignalCard key={item}>{item}</SignalCard>
                    ))
                  ) : session.entry_mode === 'empty' || session.entry_mode === 'context' ? (
                    <>
                      <SignalCard>
                        Персонализация пока не накопила сигналы. Первый полезный контекст появится
                        после поиска, открытия карточек и действий с избранным или корзиной.
                      </SignalCard>
                      {starterScenarios.slice(0, 2).map((scenario) => (
                        <Button
                          key={scenario.key}
                          onClick={() => void applyStarterScenario(scenario)}
                        >
                          Запустить: {scenario.title}
                        </Button>
                      ))}
                    </>
                  ) : (
                    <SignalCard>
                      Поиск пока использует базовый профиль пользователя. Откройте карточку,
                      добавьте позицию в избранное или корзину, чтобы усилить персонализацию.
                    </SignalCard>
                  )}
                </SignalList>
              )}
            </SidebarCard>

            <SidebarCard>
              <SidebarHeader>
                <SidebarTitle level={3}>
                  {session.role === 'supplier' ? 'Конкуренты в выдаче' : 'Закупочный контекст'}
                </SidebarTitle>
                <SidebarSubtitle>
                  {session.role === 'supplier'
                    ? 'Срез рынка по текущему запросу'
                    : 'История и текущий фокус пользователя'}
                </SidebarSubtitle>
              </SidebarHeader>
              {session.role === 'supplier' ? (
                supplierInsightsQuery.isLoading ? (
                  <Skeleton active paragraph={{ rows: 5 }} />
                ) : supplierInsightsQuery.data ? (
                  <>
                    <MetricGrid $columns={2}>
                      <MetricCard>
                        <MetricValue>
                          {supplierInsightsQuery.data.owned_catalog_items_count.toLocaleString('ru-RU')}
                        </MetricValue>
                        <MetricLabel>Позиции вашего ассортимента</MetricLabel>
                      </MetricCard>
                      <MetricCard>
                        <MetricValue>
                          {supplierInsightsQuery.data.tracked_categories_count.toLocaleString('ru-RU')}
                        </MetricValue>
                        <MetricLabel>Категорий под наблюдением</MetricLabel>
                      </MetricCard>
                      <MetricCard>
                        <MetricValue>
                          {supplierInsightsQuery.data.owned_purchase_history_count.toLocaleString('ru-RU')}
                        </MetricValue>
                        <MetricLabel>Закупок по вашему сегменту</MetricLabel>
                      </MetricCard>
                      <MetricCard>
                        <MetricValue>
                          {supplierInsightsQuery.data.top_competitors.length.toLocaleString('ru-RU')}
                        </MetricValue>
                        <MetricLabel>Ключевых конкурентов</MetricLabel>
                      </MetricCard>
                    </MetricGrid>

                    {supplierInsightsQuery.data.matched_suppliers.length ? (
                      <SignalList>
                        {supplierInsightsQuery.data.matched_suppliers.map((item) => (
                          <SignalCard key={item.id}>
                            Совпадение поставщика: {item.name} · позиций {item.catalog_items_count} · overlap {item.token_overlap}
                          </SignalCard>
                        ))}
                      </SignalList>
                    ) : null}

                    <PurchaseList>
                      {supplierInsightsQuery.data.top_demand_categories.map((item) => (
                        <PurchaseCard key={item.id}>
                          <PurchaseTitle>{item.name}</PurchaseTitle>
                          <PurchaseMeta>
                            {item.catalog_items_count.toLocaleString('ru-RU')} позиций в категории
                          </PurchaseMeta>
                          <PurchaseMeta>
                            {item.purchase_count.toLocaleString('ru-RU')} закупок по категории
                          </PurchaseMeta>
                        </PurchaseCard>
                      ))}
                    </PurchaseList>

                    <PurchaseList>
                      {supplierInsightsQuery.data.top_competitors.map((item) => (
                        <PurchaseCard key={item.id}>
                          <PurchaseTitle>{item.name}</PurchaseTitle>
                          <PurchaseMeta>
                            {item.catalog_items_count.toLocaleString('ru-RU')} позиций в каталоге
                          </PurchaseMeta>
                          <PurchaseMeta>
                            {item.purchase_history_count.toLocaleString('ru-RU')} закупок в смежных категориях
                          </PurchaseMeta>
                        </PurchaseCard>
                      ))}
                    </PurchaseList>

                    {supplierInsightsQuery.data.hot_opportunities.length ? (
                      <PurchaseList>
                        {supplierInsightsQuery.data.hot_opportunities.slice(0, 3).map((item) => (
                          <PurchaseCard key={item.ste_id}>
                            <PurchaseTitle>{item.title}</PurchaseTitle>
                            <PurchaseMeta>
                              {item.category_name} · {item.supplier_name}
                            </PurchaseMeta>
                            <PurchaseMeta>
                              {item.purchase_count.toLocaleString('ru-RU')} закупок в истории
                            </PurchaseMeta>
                          </PurchaseCard>
                        ))}
                      </PurchaseList>
                    ) : null}
                  </>
                ) : (
                  <SignalCard>
                    Для этой роли пока не удалось собрать supplier analytics.
                  </SignalCard>
                )
              ) : purchaseHistoryQuery.isLoading ? (
                <Skeleton active paragraph={{ rows: 4 }} />
              ) : (
                <>
                  <MetricGrid $columns={2}>
                    <MetricCard>
                      <MetricValue>{(purchaseHistoryQuery.data ?? []).length.toLocaleString('ru-RU')}</MetricValue>
                      <MetricLabel>Последних закупок в профиле</MetricLabel>
                    </MetricCard>
                    <MetricCard>
                      <MetricValue>{topResultCategories.length.toLocaleString('ru-RU')}</MetricValue>
                      <MetricLabel>Категорий в текущей выдаче</MetricLabel>
                    </MetricCard>
                  </MetricGrid>
                  {hasPurchaseHistory ? (
                    <PurchaseList>
                      {(purchaseHistoryQuery.data ?? []).slice(0, 4).map((item) => (
                        <PurchaseCard key={item.id}>
                          <PurchaseTitle>{item.title}</PurchaseTitle>
                          <PurchaseMeta>
                            {item.category_name} · {item.supplier_name}
                          </PurchaseMeta>
                          <PurchaseMeta>
                            {formatPurchasePrice(item.price)} · {formatPurchaseDate(item.purchased_at)}
                          </PurchaseMeta>
                        </PurchaseCard>
                      ))}
                    </PurchaseList>
                  ) : (
                    <SignalList>
                      <SignalCard>
                        История закупок пока пуста. Используйте стартовые сценарии и добавляйте
                        позиции в корзину, чтобы кабинет начал собирать рабочий контекст.
                      </SignalCard>
                      {starterScenarios.map((scenario) => (
                        <Button
                          key={scenario.key}
                          onClick={() => void applyStarterScenario(scenario)}
                        >
                          {scenario.title}
                        </Button>
                      ))}
                    </SignalList>
                  )}
                </>
              )}
            </SidebarCard>
          </Sidebar>

          <Content>
            <SectionSurface ref={catalogSectionRef}>
              <TabsRow>
                {session.role === 'supplier' ? (
                  <TabButton $active={false} onClick={() => navigate('/supplier')}>
                    Dashboard поставщика
                  </TabButton>
                ) : null}
                <TabButton
                  $active={activeTab === 'catalog'}
                  onClick={() => {
                    setActiveTab('catalog')
                    setFavoritesPage(1)
                  }}
                >
                  Каталог
                </TabButton>
                <TabButton
                  $active={activeTab === 'favorites'}
                  onClick={() => {
                    setActiveTab('favorites')
                    setFavoritesPage(1)
                  }}
                >
                  Избранное ({favoritesQuery.data?.length ?? 0})
                </TabButton>
                <TabButton
                  $active={activeTab === 'compare'}
                  onClick={() => {
                    setActiveTab('compare')
                    setFavoritesPage(1)
                  }}
                >
                  Сравнение ({comparisonQuery.data?.length ?? 0})
                </TabButton>
                <TabButton $active={false} onClick={() => navigate('/cart')}>
                  Корзина ({cartQuery.data?.length ?? 0})
                </TabButton>
              </TabsRow>

              <SectionHeaderBar $padding="content" $bordered>
                <SectionHeadingStack>
                  <SectionHeading>
                    {activeTab === 'catalog'
                      ? 'Результаты каталога'
                      : activeTab === 'favorites'
                      ? 'Избранные позиции'
                      : 'Сравнение товаров'}
                  </SectionHeading>
                  <SectionHeadingHint>
                    {activeTab === 'catalog'
                      ? searchState.kind === 'results'
                        ? `Запрос: ${searchState.response.meta.query}`
                        : showOnboardingStrip && !hasProfileSignals
                        ? 'Кабинет пока пустой: выберите стартовый сценарий выше или выполните первый поиск'
                        : 'Стартовая лента показывает персональные и популярные позиции каталога'
                      : activeTab === 'favorites'
                      ? (favoritesQuery.data?.length ?? 0)
                        ? 'Позиции, которые пользователь отметил для быстрого возврата'
                        : 'Сохраните сюда позиции из каталога, чтобы быстро вернуться к ним позже'
                      : visibleCompareItems.length
                      ? 'До 4 позиций для сравнения характеристик'
                      : 'Добавьте сюда 2-4 позиции из каталога, чтобы увидеть отличия по параметрам'}
                  </SectionHeadingHint>
                </SectionHeadingStack>

                <SearchMetaGroup>
                  {searchState.kind === 'results' && activeTab === 'catalog' ? (
                    <>
                      <Select
                        size="middle"
                        value={sortMode}
                        style={{ minWidth: 210 }}
                        onChange={(value) => handleSortChange(value as SortMode)}
                        options={[
                          { value: 'relevance', label: 'Сортировка: по релевантности' },
                          { value: 'title_asc', label: 'Сортировка: по названию' },
                          { value: 'supplier_asc', label: 'Сортировка: по поставщику' },
                        ]}
                      />
                      <StatusPill $tone="accent">Режим: {searchState.response.meta.ranking_mode}</StatusPill>
                      {searchState.response.meta.corrected_query ? (
                        <StatusPill $tone="info">Исправлено: {searchState.response.meta.corrected_query}</StatusPill>
                      ) : null}
                      {searchState.response.meta.applied_synonyms.length ? (
                        <StatusPill $tone="purple">
                          Синонимы: {searchState.response.meta.applied_synonyms.slice(0, 2).join(', ')}
                        </StatusPill>
                      ) : null}
                    </>
                  ) : null}
                </SearchMetaGroup>
              </SectionHeaderBar>

              {activeTab === 'catalog' ? (
                <>
                  {searchState.kind === 'loading' || (searchState.kind === 'idle' && feedQuery.isLoading) ? (
                    <div style={{ padding: 28 }}>
                      <Skeleton active paragraph={{ rows: 8 }} />
                    </div>
                  ) : searchState.kind === 'error' ? (
                    <div style={{ padding: 28 }}>
                      <Empty description={searchState.message} />
                    </div>
                  ) : searchState.kind === 'results' ? (
                    <>
                      {searchState.response.meta.explanations.length ? (
                        <ExplanationBand>
                          {searchState.response.meta.explanations.map((item) => (
                            <ExplanationChip key={item}>{item}</ExplanationChip>
                          ))}
                        </ExplanationBand>
                      ) : null}
                      {searchState.response.items.length ? (
                        <>
                          <ResultGrid>
                            {visibleCatalogItems
                              .slice((catalogPage - 1) * CATALOG_PAGE_SIZE, catalogPage * CATALOG_PAGE_SIZE)
                              .map((item, index) =>
                                renderProductCard(
                                  {
                                    id: item.id,
                                    title: item.title,
                                    supplier: item.supplier,
                                    category: item.category,
                                    score: item.score,
                                    reasons: item.reasons,
                                  },
                                  {
                                    trackResultClick: true,
                                    showReasons: true,
                                    rankPosition: (catalogPage - 1) * CATALOG_PAGE_SIZE + index + 1,
                                  },
                                ),
                              )}
                          </ResultGrid>
                          {searchState.response.items.length > CATALOG_PAGE_SIZE ? (
                            <div style={{ padding: '0 20px 24px' }}>
                              <Pagination
                                current={catalogPage}
                                pageSize={CATALOG_PAGE_SIZE}
                                total={searchState.response.items.length}
                                onChange={handleCatalogPageChange}
                                showSizeChanger={false}
                              />
                            </div>
                          ) : null}
                        </>
                      ) : (
                        <div style={{ padding: 28 }}>
                          <Empty description="Ничего не найдено. Попробуйте убрать strict match или сменить запрос." />
                        </div>
                      )}
                    </>
                  ) : (
                    feedQuery.data?.items.length ? (
                      <>
                        <ExplanationBand>
                          <ExplanationChip>Лента по умолчанию учитывает историю закупок, избранное и популярные позиции каталога.</ExplanationChip>
                          <ExplanationChip>Пользователь сразу видит, что можно открыть, сравнить или добавить в подборку без первого запроса.</ExplanationChip>
                        </ExplanationBand>
                        <ResultGrid>
                          {feedQuery.data.items.map((item) =>
                            renderProductCard(
                              {
                                id: item.id,
                                title: item.title,
                                supplier: item.supplier_name,
                                category: item.category_name,
                                statusLabel: 'В стартовой ленте',
                                secondaryLabel: item.feed_reason,
                              },
                              {
                                trackResultClick: false,
                                showReasons: false,
                              },
                            ),
                          )}
                        </ResultGrid>
                        {feedQuery.data.total > CATALOG_PAGE_SIZE ? (
                          <div style={{ padding: '0 20px 24px' }}>
                            <Pagination
                              current={catalogPage}
                              pageSize={CATALOG_PAGE_SIZE}
                              total={feedQuery.data.total}
                              onChange={handleCatalogPageChange}
                              showSizeChanger={false}
                            />
                          </div>
                        ) : null}
                      </>
                    ) : (
                      <div style={{ padding: 28 }}>
                        <Empty
                          description="Лента пока пуста. Попробуйте выбрать категорию или выполнить поиск по каталогу."
                        />
                      </div>
                    )
                  )}
                </>
              ) : activeTab === 'compare' ? (
                visibleCompareItems.length ? (
                  <CompareTable>
                    <CompareLead>
                      <CompareLeadTitle>Compare-витрина</CompareLeadTitle>
                      Сравнение построено как расширение каталога: сверху те же product-карточки,
                      снизу структурированная таблица параметров. Подсвеченные строки сразу
                      показывают, где позиции реально расходятся.
                    </CompareLead>
                    <CompareCards>
                      {visibleCompareItems.map((item) => {
                        const [from, to] = buildCardTone(item.item.id)
                        const compareInFavorites = favoriteIds.has(item.item.id)
                        const compareInCart = cartMap.has(item.item.id)
                        return (
                          <CompareSubjectCard key={item.id}>
                            <CompareSubjectTop>
                              <CompareSubjectStamp>ID СТЕ {item.item.id}</CompareSubjectStamp>
                              <CompareSubjectSignalRow>
                                {compareInFavorites ? (
                            <ProductContextChip $tone="accent">Избранное</ProductContextChip>
                                ) : null}
                                <ProductContextChip $tone="warning">Сравнение</ProductContextChip>
                                {compareInCart ? (
                                  <ProductContextChip $tone="success">В корзине</ProductContextChip>
                                ) : null}
                              </CompareSubjectSignalRow>
                            </CompareSubjectTop>
                            <CompareSubjectVisual $from={from} $to={to}>
                              <ProductVisualLabel>{buildCardLabel(item.item.title)}</ProductVisualLabel>
                            </CompareSubjectVisual>
                            <CompareSubjectTitle>{item.item.title}</CompareSubjectTitle>
                            <CompareSubjectMeta>
                              <CompareMetaCard>
                                <CompareMetaLabel>Категория</CompareMetaLabel>
                                <CompareMetaValue>{item.item.category_name}</CompareMetaValue>
                              </CompareMetaCard>
                              <CompareMetaCard>
                                <CompareMetaLabel>Поставщик</CompareMetaLabel>
                                <CompareMetaValue>{item.item.supplier_name}</CompareMetaValue>
                              </CompareMetaCard>
                            </CompareSubjectMeta>
                            <CompareSubjectFooter>
                              <ProductStatusRow>
                                <ProductStatusCard>
                                  <ProductStatusValue>В сравнении</ProductStatusValue>
                                  <ProductStatusLabel>Состояние позиции</ProductStatusLabel>
                                </ProductStatusCard>
                                <ProductStatusCard>
                                  <ProductStatusValue>
                                    {compareInCart ? 'Готово к подборке' : 'Проверка различий'}
                                  </ProductStatusValue>
                                  <ProductStatusLabel>Рабочий контекст</ProductStatusLabel>
                                </ProductStatusCard>
                              </ProductStatusRow>
                              <ProductReasonPanel>
                                <ProductReasonHeader>Фокус сравнения</ProductReasonHeader>
                                <ProductReasonText>
                                  {compareDifferenceLabels.size
                                    ? 'Подсвеченные строки в таблице ниже показывают отличия по статусу, поставщику и атрибутам.'
                                    : 'Текущий набор параметров почти совпадает, различия минимальны.'}
                                </ProductReasonText>
                              </ProductReasonPanel>
                            </CompareSubjectFooter>
                            <ProductActions>
                              <SurfaceButton
                                $tone="neutral"
                                $emphasis="soft"
                                size="small"
                                onClick={() => navigate(buildProductPath(item.item.id, currentSessionId))}
                              >
                                Карточка
                              </SurfaceButton>
                              <SurfaceButton
                                $tone="danger"
                                $emphasis="soft"
                                size="small"
                                onClick={() =>
                                  comparisonMutation.mutate({
                                    steId: item.ste_id,
                                    active: true,
                                  })
                                }
                              >
                                Убрать
                              </SurfaceButton>
                            </ProductActions>
                          </CompareSubjectCard>
                        )
                      })}
                      {Array.from({
                        length: Math.max(0, 4 - visibleCompareItems.length),
                      }).map((_, index) => (
                        <CompareSubjectCard key={`empty-card-${index}`}>
                          <CompareSubjectTop>
                            <CompareSubjectStamp>Свободный слот</CompareSubjectStamp>
                          </CompareSubjectTop>
                          <EmptyStateBlock $gap={14}>
                            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Добавьте позицию" />
                            <EmptyStateText $size="md">
                              Слот резервирует место под еще одну карточку. Добавьте позицию из
                              каталога или из shortlist, чтобы расширить сравнение.
                            </EmptyStateText>
                          </EmptyStateBlock>
                        </CompareSubjectCard>
                      ))}
                    </CompareCards>
                    <div style={{ overflow: 'auto' }}>
                      <CompareGrid>
                        <CompareCell $header>
                          <CompareCellLabel>Параметр</CompareCellLabel>
                          <CompareCellHint>Общие и атрибутивные поля</CompareCellHint>
                        </CompareCell>
                        {visibleCompareItems.map((item) => (
                          <CompareCell $header key={item.id}>
                            <CompareCellLabel>{item.item.title}</CompareCellLabel>
                            <CompareCellHint>{item.item.id}</CompareCellHint>
                          </CompareCell>
                        ))}
                        {Array.from({
                          length: Math.max(0, 4 - visibleCompareItems.length),
                        }).map((_, index) => (
                          <CompareCell key={`empty-${index}`}>Пусто</CompareCell>
                        ))}

                        {compareRowLabels.map((label) => (
                          <Fragment key={label}>
                            <CompareCell $header>
                              <CompareCellLabel>{label}</CompareCellLabel>
                              <CompareCellHint>
                                {compareDifferenceLabels.has(label) ? 'Есть различия' : 'Совпадает'}
                              </CompareCellHint>
                            </CompareCell>
                            {visibleCompareItems.map((item) => (
                              <CompareCell key={`${item.id}-${label}`} $emphasis={compareDifferenceLabels.has(label)}>
                                {label === 'Категория'
                                  ? item.item.category_name
                                  : label === 'Поставщик'
                                  ? item.item.supplier_name
                                  : label === 'Статус'
                                  ? item.item.status
                                  : item.item.attributes[label] ?? '—'}
                              </CompareCell>
                            ))}
                            {Array.from({
                              length: Math.max(0, 4 - visibleCompareItems.length),
                            }).map((_, index) => (
                              <CompareCell key={`${label}-empty-${index}`}>—</CompareCell>
                            ))}
                          </Fragment>
                        ))}
                      </CompareGrid>
                    </div>
                  </CompareTable>
                ) : (
                  <div style={{ padding: 28 }}>
                    <EmptyStateBlock $gap={14}>
                      <Empty description="Добавьте товары в сравнение из результатов поиска." />
                      <EmptyStateText $size="md">
                        Сравнение собирается из карточек каталога. Откройте готовый сценарий,
                        отметьте 2-4 позиции и вернитесь сюда для просмотра различий.
                      </EmptyStateText>
                      <CollectionActionRow>
                        <Button onClick={() => setActiveTab('catalog')}>Открыть каталог</Button>
                        {collectionStarterScenarios.slice(0, 2).map((scenario) => (
                          <Button
                            key={scenario.key}
                            type="primary"
                            ghost
                            onClick={() => openCollectionStarterScenario(scenario)}
                          >
                            Сценарий: {scenario.title}
                          </Button>
                        ))}
                      </CollectionActionRow>
                    </EmptyStateBlock>
                  </div>
                )
              ) : activeCollectionItems.length ? (
                <>
                  <ResultGrid>
                    {pagedFavoriteItems.map((item) =>
                      renderProductCard({
                        id: item.id,
                        title: item.title,
                        supplier: item.supplier_name,
                        category: item.category_name,
                        statusLabel: activeTab === 'favorites' ? 'В избранном' : 'В сравнении',
                        secondaryLabel:
                          activeTab === 'favorites'
                            ? 'Быстрый возврат'
                            : 'Готово к сравнению',
                      }),
                    )}
                  </ResultGrid>
                  {activeCollectionItems.length > FAVORITES_PAGE_SIZE ? (
                    <div style={{ padding: '0 20px 24px' }}>
                      <Pagination
                        current={effectiveFavoritesPage}
                        pageSize={FAVORITES_PAGE_SIZE}
                        total={activeCollectionItems.length}
                        onChange={handleFavoritesPageChange}
                        showSizeChanger={false}
                      />
                    </div>
                  ) : null}
                </>
              ) : (
                <div style={{ padding: 28 }}>
                  <EmptyStateBlock $gap={14}>
                    <Empty
                      description={
                        activeTab === 'favorites'
                          ? 'Пока нет избранных позиций.'
                          : 'Пока нет позиций в этом разделе.'
                      }
                    />
                    <EmptyStateText $size="md">
                      {activeTab === 'favorites'
                        ? 'Избранное помогает быстро собирать shortlist. Добавьте сюда позиции из каталога или из стартового сценария.'
                        : 'Раздел пока пуст. Откройте каталог и начните с готового сценария, чтобы наполнить его полезными позициями.'}
                    </EmptyStateText>
                    <CollectionActionRow>
                      <Button onClick={() => setActiveTab('catalog')}>Перейти в каталог</Button>
                      {collectionStarterScenarios.slice(0, 2).map((scenario) => (
                        <Button
                          key={scenario.key}
                          type="primary"
                          ghost
                          onClick={() => openCollectionStarterScenario(scenario)}
                        >
                          Запустить: {scenario.title}
                        </Button>
                      ))}
                    </CollectionActionRow>
                  </EmptyStateBlock>
                </div>
              )}
            </SectionSurface>

            <SectionSurface>
              <SectionHeaderBar $padding="content" $bordered>
                <SectionHeadingStack>
                  <SectionHeading>Подсказки профиля</SectionHeading>
                  <SectionHeadingHint>
                    {hasProfileSignals || hasSearchHistory
                      ? 'Последние запросы и популярные категории для выбранного пользователя'
                      : 'Пока профиль пустой: здесь появятся ваши рабочие категории, запросы и быстрые возвраты'}
                  </SectionHeadingHint>
                </SectionHeadingStack>
              </SectionHeaderBar>
              <div style={{ padding: 20, display: 'grid', gap: 16 }}>
                {hasProfileSignals || hasSearchHistory ? (
                  <>
                    <HintSurface>
                      <HintText>
                        {session.entry_mode === 'context'
                          ? 'Организационный контекст уже влияет на выдачу. Новые запросы и действия помогут быстрее превратить его в персональный профиль.'
                          : 'Этот блок собирает рабочий контекст пользователя: частые категории, повторяемые запросы и темы, к которым удобно возвращаться.'}
                      </HintText>
                      {session.entry_note ? <HintText>{session.entry_note}</HintText> : null}
                    </HintSurface>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {(profileQuery.data?.top_categories ?? []).slice(0, 8).map((item) => (
                        <Tag key={item} color="processing">
                          {item}
                        </Tag>
                      ))}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {(historyQuery.data?.items ?? []).slice(0, 6).map((item: SearchHistoryItem) => (
                        <Button key={item.id} onClick={() => openActivitySearch(item.query)}>
                          {item.query}
                        </Button>
                      ))}
                    </div>
                  </>
                ) : (
                  <HintSurface>
                    <HintText>
                      Профиль еще не накопил поисковые сигналы. После первых запросов здесь появятся
                      категории, к которым пользователь чаще всего возвращается, и быстрые кнопки
                      для повторного запуска полезных сценариев.
                    </HintText>
                    {session.entry_note ? <HintText>{session.entry_note}</HintText> : null}
                    <CollectionActionRow>
                      {collectionStarterScenarios.map((scenario) => (
                        <Button
                          key={scenario.key}
                          type="primary"
                          ghost
                          onClick={() => openCollectionStarterScenario(scenario)}
                        >
                          Старт: {scenario.title}
                        </Button>
                      ))}
                    </CollectionActionRow>
                  </HintSurface>
                )}
              </div>
            </SectionSurface>

            <SectionSurface>
              <SectionHeaderBar $padding="content" $bordered>
                <SectionHeadingStack>
                  <SectionHeading>Последние действия</SectionHeading>
                  <SectionHeadingHint>
                    Живая лента недавних поисковых и закупочных действий пользователя
                  </SectionHeadingHint>
                </SectionHeadingStack>
                <ActivityControls>
                  <Button
                    danger
                    ghost
                    loading={clearHistoryMutation.isPending}
                    disabled={!historyQuery.data?.items?.length && !activityQuery.data?.items?.length}
                    onClick={() => clearHistoryMutation.mutate()}
                  >
                    Очистить историю
                  </Button>
                  <Select
                    size="middle"
                    value={activityFilter}
                    style={{ minWidth: 180 }}
                    onChange={(value) => setActivityFilter(value as ActivityFilter)}
                    options={activityFilterOptions}
                  />
                </ActivityControls>
              </SectionHeaderBar>
              <div style={{ padding: 20, display: 'grid', gap: 16 }}>
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
                          <StatusPill $tone={getActivityPillTone(item.event_type)}>{item.event_type}</StatusPill>
                          {item.query ? <StatusPill $tone="neutral">{item.query}</StatusPill> : null}
                          {item.ste_title ? <StatusPill $tone="info">{item.ste_title}</StatusPill> : null}
                        </ActivityMeta>
                        <ActivityText>{item.description}</ActivityText>
                        <InlineActionRow>
                          {item.query ? (
                            <SurfaceButton $tone="neutral" $emphasis="soft" size="small" onClick={() => openActivitySearch(item.query ?? '')}>
                              Повторить поиск
                            </SurfaceButton>
                          ) : null}
                          {item.ste_id ? (
                            <SurfaceButton $tone="accent" $emphasis="soft" size="small" onClick={() => openActivityProduct(item.ste_id ?? '')}>
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
                  <HintSurface>
                    <HintText>
                      Для выбранного фильтра пока нет событий. Переключите тип действий или
                      продолжите сценарий в каталоге, чтобы собрать новые сигналы.
                    </HintText>
                    <CollectionActionRow>
                      <Button onClick={() => setActivityFilter('all')}>Показать все действия</Button>
                      {collectionStarterScenarios.slice(0, 2).map((scenario) => (
                        <Button
                          key={scenario.key}
                          type="primary"
                          ghost
                          onClick={() => openCollectionStarterScenario(scenario)}
                        >
                          Сценарий: {scenario.title}
                        </Button>
                      ))}
                    </CollectionActionRow>
                  </HintSurface>
                ) : (
                  <HintSurface>
                    <HintText>
                      История действий пока пуста. После первых поисков, открытий карточек,
                      добавлений в избранное и корзину здесь появится живая лента поведения
                      пользователя.
                    </HintText>
                    {session.entry_note ? <HintText>{session.entry_note}</HintText> : null}
                    <CollectionActionRow>
                      {collectionStarterScenarios.map((scenario) => (
                        <Button
                          key={scenario.key}
                          type="primary"
                          ghost
                          onClick={() => openCollectionStarterScenario(scenario)}
                        >
                          Начать с: {scenario.title}
                        </Button>
                      ))}
                    </CollectionActionRow>
                  </HintSurface>
                )}
              </div>
            </SectionSurface>
          </Content>
        </WorkspaceGrid>
      </Main>

    </PortalShell>
  )
}

export default HomePage
