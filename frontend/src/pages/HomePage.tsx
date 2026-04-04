import {
  AppstoreOutlined,
  BellOutlined,
  BulbOutlined,
  HeartFilled,
  HeartOutlined,
  MenuOutlined,
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
  getActivityColor,
  getActivityFilterKey,
  type ActivityFilter,
} from '@entities/search/lib/activity'
import { buildAutocompleteOptions, formatSearchReason } from '@entities/search/lib/formatters'
import {
  addCartItem,
  addComparisonItem,
  addFavorite,
  createSearchEvent,
  createSearchImpressions,
  getCartItems,
  getCategories,
  getSearchActivity,
  getCatalogFeed,
  getCatalogSummary,
  getComparisonItems,
  getDemoUsers,
  getFavorites,
  getPurchaseHistory,
  getSearchHistory,
  getSearchProfile,
  getSearchSuggestions,
  getSupplierInsights,
  getSuppliers,
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
  type FavoriteItem,
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
import PortalShell from '@widgets/portal-shell/PortalShell'

const STORAGE_KEYS = {
  search: 'portal-search-query-v2',
  category: 'portal-search-category-v2',
  supplier: 'portal-search-supplier-v2',
  strict: 'portal-search-strict-v2',
  sort: 'portal-search-sort-v1',
} as const

const CATALOG_PAGE_SIZE = 9
const FAVORITES_PAGE_SIZE = 8

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
  gap: 14px;
  min-width: 0;
`

const BrandMark = styled.div`
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background:
    linear-gradient(135deg, #1f4e86 0%, #335d90 45%, #d93c30 45%, #d93c30 72%, #f0f4f8 72%);
  box-shadow: inset 0 0 0 4px rgba(255, 255, 255, 0.82);
`

const BrandText = styled.div`
  display: grid;
  gap: 2px;
`

const BrandTitle = styled.span`
  color: #cb3428;
  font-size: 24px;
  font-weight: 800;
  line-height: 1;
  text-transform: uppercase;
`

const BrandSubtitle = styled.span`
  color: #95a2b1;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
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

const OnboardingStrip = styled.section`
  display: grid;
  gap: 16px;
  margin-top: 18px;
  padding: 18px 20px;
  border: 1px solid #d9e0e8;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(244, 248, 253, 0.98) 100%);
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
  color: #5f7085;
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
  border: 1px solid #dbe4ed;
  color: #273a53;
  font: inherit;
  text-align: left;
  background: #fff;
  cursor: pointer;

  &:hover {
    border-color: #2f4f84;
    background: #f7fbff;
  }
`

const OnboardingCardTitle = styled.span`
  color: #2b4365;
  font-size: 15px;
  font-weight: 800;
`

const OnboardingCardText = styled.span`
  color: #66778c;
  font-size: 13px;
  line-height: 1.45;
`

const OnboardingCardAction = styled.span`
  color: #2f4f84;
  font-size: 13px;
  font-weight: 800;
  text-transform: uppercase;
`

const CollectionEmptyState = styled.div`
  display: grid;
  gap: 14px;
  justify-items: start;
`

const CollectionEmptyText = styled.span`
  color: #64748a;
  font-size: 14px;
  line-height: 1.5;
`

const CollectionActionRow = styled.div`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
`

const HintPanel = styled.div`
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #dde6ef;
  background: #fbfcfe;
`

const HintText = styled.span`
  color: #64748a;
  font-size: 14px;
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

const SummaryGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
`

const SummaryStat = styled.div`
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border: 1px solid #e2e8ef;
  background: #fbfcfd;
`

const SummaryValue = styled.span`
  color: #24364f;
  font-size: 20px;
  font-weight: 800;
`

const SummaryLabel = styled.span`
  color: #728196;
  font-size: 12px;
  line-height: 1.4;
`

const Content = styled.section`
  display: grid;
  gap: 18px;
`

const SectionCard = styled.section`
  border: 1px solid #d9e0e8;
  background: #fff;
  box-shadow: 0 10px 24px rgba(74, 92, 117, 0.05);
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

const ContentHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 18px 20px;
  border-bottom: 1px solid #e1e7ee;
`

const ContentTitle = styled(Typography.Title)`
  && {
    margin: 0;
    color: #314158;
    font-size: 18px;
    font-weight: 700;
  }
`

const ContentHint = styled(Typography.Text)`
  color: #6a798c;
  font-size: 13px;
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
  gap: 10px;
  padding: 18px 20px 14px;
`

const ProductTechMeta = styled.div`
  display: grid;
  gap: 4px;
`

const ProductTechLine = styled.div`
  color: #6b7c91;
  font-size: 12px;
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
  gap: 5px;
  color: #4f5f74;
  font-size: 14px;
  line-height: 1.45;
`

const MetaLabel = styled.span`
  color: #24364f;
  font-weight: 700;
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
  padding: 16px 18px;
  border: 1px solid #dbe3ec;
  color: #607085;
  background: #fbfcfe;
  font-size: 13px;
  line-height: 1.55;
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
  gap: 12px;
  min-height: 240px;
  padding: 16px;
  border: 1px solid #dbe3ec;
  background: #fff;
`

const CompareSubjectVisual = styled.div<{ $from: string; $to: string }>`
  display: grid;
  place-items: center;
  min-height: 124px;
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
  gap: 4px;
  color: #66778b;
  font-size: 12px;
  line-height: 1.45;
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
  background: ${({ $header, $emphasis }) => ($header ? '#f7f9fc' : $emphasis ? '#fff8eb' : '#fff')};
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
  const [selectedUserId, setSelectedUserId] = useState('')
  const [messageApi, contextHolder] = message.useMessage()

  const demoUsersQuery = useQuery({
    queryKey: ['demo-users'],
    queryFn: getDemoUsers,
  })

  const effectiveSelectedUserId = selectedUserId || demoUsersQuery.data?.[0]?.id || ''

  const loginMutation = useMutation({
    mutationFn: loginDemoUser,
    onSuccess: (data) => {
      onLogin(data)
    },
    onError: (error) => {
      const description = error instanceof Error ? error.message : 'Не удалось выполнить вход'
      void messageApi.error(description)
    },
  })

  return (
    <Screen>
      {contextHolder}
      <LoginShell>
        <LoginHero>
          <div style={{ display: 'grid', gap: 18 }}>
            <Brand>
              <BrandMark />
              <BrandText>
                <BrandTitle>Портал</BrandTitle>
                <BrandSubtitle>Поставщиков 2026</BrandSubtitle>
              </BrandText>
            </Brand>

            <Typography.Title level={1} style={{ margin: 0, color: '#2b3950', fontSize: 42 }}>
              Вход в демо-кабинет закупок
            </Typography.Title>
            <Typography.Paragraph style={{ margin: 0, color: '#607085', fontSize: 18 }}>
              Выберите готового пользователя и зайдите в систему без пароля. Кабинет
              поддерживает роли заказчика и поставщика, а каталог построен в визуальном
              стиле платформы из Figma UI kit.
            </Typography.Paragraph>

            <LoginHintList>
              <LoginHint>Заказчик ищет СТЕ, добавляет позиции в избранное, сравнение и корзину.</LoginHint>
              <LoginHint>Поставщик видит тот же каталог и может анализировать конкурентов и спрос.</LoginHint>
              <LoginHint>Поиск учитывает опечатки, синонимы и свежие действия пользователя.</LoginHint>
            </LoginHintList>
          </div>

          <div style={{ display: 'grid', gap: 18 }}>
            {demoUsersQuery.isLoading ? (
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
            )}

            <Button
              type="primary"
              size="large"
              loading={loginMutation.isPending}
              disabled={!effectiveSelectedUserId}
              onClick={() => {
                if (!effectiveSelectedUserId) {
                  return
                }
                loginMutation.mutate(effectiveSelectedUserId)
              }}
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
    window.localStorage.setItem(STORAGE_KEYS.strict, String(strictMatch))
    window.localStorage.setItem(STORAGE_KEYS.sort, sortMode)
  }, [searchValue, selectedCategoryId, selectedSupplierId, strictMatch, sortMode])

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

  const feedQuery = useQuery<CatalogFeedResponse>({
    queryKey: [
      'catalog-feed',
      session.user_id,
      selectedCategoryId,
      selectedSupplierId,
      catalogPage,
    ],
    queryFn: () =>
      getCatalogFeed({
        actor,
        limit: CATALOG_PAGE_SIZE,
        offset: (catalogPage - 1) * CATALOG_PAGE_SIZE,
        category_id: selectedCategoryId || undefined,
        supplier_id: selectedSupplierId || undefined,
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
      strictMatch?: boolean
    },
  ) {
    const query = (nextQuery ?? searchValue).trim()
    const effectiveCategoryId = (overrides?.categoryId ?? selectedCategoryId) || undefined
    const effectiveSupplierId = (overrides?.supplierId ?? selectedSupplierId) || undefined
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
    setStrictMatch(Boolean(scenario.strictMatch))
    setActiveTab('catalog')
    setCatalogPage(1)
    await runSearch(scenario.query, undefined, {
      categoryId: scenario.categoryId,
      supplierId: undefined,
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
    void applyStarterScenario(scenario)
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
          <ProductTechMeta>
            <ProductTechLine>
              <MetaLabel>Поставщик:</MetaLabel> {item.supplier}
            </ProductTechLine>
            <ProductTechLine>
              <MetaLabel>Категория:</MetaLabel> {item.category}
            </ProductTechLine>
          </ProductTechMeta>
          <ProductMeta>
            {typeof item.score === 'number' ? (
              <div>
                <MetaLabel>Релевантность:</MetaLabel> {item.score.toFixed(2)}
              </div>
            ) : null}
            {options?.showReasons && item.reasons?.length ? (
              <div>
                <MetaLabel>Почему показано:</MetaLabel> {item.reasons
                  .slice(0, 2)
                  .map((reason) => formatSearchReason(reason))
                  .join(', ')}
              </div>
            ) : (
              <div>
                <MetaLabel>Статус:</MetaLabel> доступно для сравнения и закупочной подборки
              </div>
            )}
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
            <Button
              icon={<ShoppingCartOutlined />}
              onClick={() =>
                cartMutation.mutate({
                  steId: item.id,
                  quantity: 1,
                })
              }
            >
              {inCart ? 'В корзине' : 'В корзину'}
            </Button>
            <Button danger onClick={markIrrelevant}>
              Нерелевантно
            </Button>
            <Button onClick={openDetails}>Карточка</Button>
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
          <HeaderTool type="button" aria-label="menu">
            <MenuOutlined />
          </HeaderTool>
          <HeaderTool type="button" aria-label="search">
            <SearchOutlined />
          </HeaderTool>
          <HeaderTool type="button" aria-label="support">
            <BellOutlined />
          </HeaderTool>
          <HeaderTool type="button" aria-label="ideas">
            <BulbOutlined />
          </HeaderTool>
          <HeaderTool type="button" aria-label="favorites">
            <Badge count={favoritesQuery.data?.length ?? 0} size="small">
              <HeartOutlined />
            </Badge>
          </HeaderTool>
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
          <SearchRow>
            <CatalogButton icon={<AppstoreOutlined />}>Каталог</CatalogButton>

            <SearchInputWrap>
              <SearchAutocomplete
                options={buildAutocompleteOptions(suggestionsQuery.data?.items ?? [])}
                value={searchValue}
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

            <Button
              icon={<StarOutlined />}
              onClick={() => {
                setActiveTab('favorites')
                setFavoritesPage(1)
              }}
            >
              Есть предложения
            </Button>
          </SearchRow>

          <SearchMetaRow>
            <SearchMetaGroup>
              <Tag color={session.role === 'supplier' ? 'orange' : 'blue'}>
                {session.role === 'supplier' ? 'Поставщик' : 'Заказчик'}
              </Tag>
              <Tag>{session.persona}</Tag>
              <Tag color={strictMatch ? 'red' : 'default'}>
                {strictMatch ? 'Strict match' : 'Мягкий поиск'}
              </Tag>
            </SearchMetaGroup>

            <SearchMetaGroup>
              <Button type={strictMatch ? 'primary' : 'default'} onClick={toggleStrictMatch}>
                {strictMatch ? 'Строгое совпадение' : 'Включить strict match'}
              </Button>
            </SearchMetaGroup>
          </SearchMetaRow>
        </SearchStrip>

        {showOnboardingStrip ? (
          <OnboardingStrip>
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
                  key={scenario.key}
                  type="button"
                  onClick={() => void applyStarterScenario(scenario)}
                >
                  <Tag color="blue">Стартовый сценарий</Tag>
                  <OnboardingCardTitle>{scenario.title}</OnboardingCardTitle>
                  <OnboardingCardText>{scenario.description}</OnboardingCardText>
                  <OnboardingCardAction>Открыть выдачу</OnboardingCardAction>
                </OnboardingCard>
              ))}
            </OnboardingGrid>
          </OnboardingStrip>
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
                  Фильтры работают поверх каталога СТЕ и не меняют профиль пользователя.
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
                        strict_match: strictMatch,
                      },
                      actor,
                    })
                  }
                  setSelectedCategoryId('')
                  setSelectedSupplierId('')
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
                  <SummaryGrid>
                    <SummaryStat>
                      <SummaryValue>{summaryQuery.data.ste_items_count.toLocaleString('ru-RU')}</SummaryValue>
                      <SummaryLabel>Позиций СТЕ</SummaryLabel>
                    </SummaryStat>
                    <SummaryStat>
                      <SummaryValue>{summaryQuery.data.categories_count.toLocaleString('ru-RU')}</SummaryValue>
                      <SummaryLabel>Категорий</SummaryLabel>
                    </SummaryStat>
                    <SummaryStat>
                      <SummaryValue>{summaryQuery.data.suppliers_count.toLocaleString('ru-RU')}</SummaryValue>
                      <SummaryLabel>Поставщиков</SummaryLabel>
                    </SummaryStat>
                    <SummaryStat>
                      <SummaryValue>{summaryQuery.data.purchase_history_count.toLocaleString('ru-RU')}</SummaryValue>
                      <SummaryLabel>Записей истории закупок</SummaryLabel>
                    </SummaryStat>
                    <SummaryStat>
                      <SummaryValue>{summaryQuery.data.favorites_count.toLocaleString('ru-RU')}</SummaryValue>
                      <SummaryLabel>Избранное пользователя</SummaryLabel>
                    </SummaryStat>
                    <SummaryStat>
                      <SummaryValue>{summaryQuery.data.cart_count.toLocaleString('ru-RU')}</SummaryValue>
                      <SummaryLabel>Позиций в корзине</SummaryLabel>
                    </SummaryStat>
                  </SummaryGrid>

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
                    <SummaryGrid>
                      <SummaryStat>
                        <SummaryValue>
                          {supplierInsightsQuery.data.owned_catalog_items_count.toLocaleString('ru-RU')}
                        </SummaryValue>
                        <SummaryLabel>Позиции вашего ассортимента</SummaryLabel>
                      </SummaryStat>
                      <SummaryStat>
                        <SummaryValue>
                          {supplierInsightsQuery.data.tracked_categories_count.toLocaleString('ru-RU')}
                        </SummaryValue>
                        <SummaryLabel>Категорий под наблюдением</SummaryLabel>
                      </SummaryStat>
                      <SummaryStat>
                        <SummaryValue>
                          {supplierInsightsQuery.data.owned_purchase_history_count.toLocaleString('ru-RU')}
                        </SummaryValue>
                        <SummaryLabel>Закупок по вашему сегменту</SummaryLabel>
                      </SummaryStat>
                      <SummaryStat>
                        <SummaryValue>
                          {supplierInsightsQuery.data.top_competitors.length.toLocaleString('ru-RU')}
                        </SummaryValue>
                        <SummaryLabel>Ключевых конкурентов</SummaryLabel>
                      </SummaryStat>
                    </SummaryGrid>

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
                  <SummaryGrid>
                    <SummaryStat>
                      <SummaryValue>{(purchaseHistoryQuery.data ?? []).length.toLocaleString('ru-RU')}</SummaryValue>
                      <SummaryLabel>Последних закупок в профиле</SummaryLabel>
                    </SummaryStat>
                    <SummaryStat>
                      <SummaryValue>{topResultCategories.length.toLocaleString('ru-RU')}</SummaryValue>
                      <SummaryLabel>Категорий в текущей выдаче</SummaryLabel>
                    </SummaryStat>
                  </SummaryGrid>
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
            <SectionCard>
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

              <ContentHeader>
                <div style={{ display: 'grid', gap: 4 }}>
                  <ContentTitle level={2}>
                    {activeTab === 'catalog'
                      ? 'Результаты каталога'
                      : activeTab === 'favorites'
                      ? 'Избранные позиции'
                      : 'Сравнение товаров'}
                  </ContentTitle>
                  <ContentHint>
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
                  </ContentHint>
                </div>

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
                      <Tag color="processing">Режим: {searchState.response.meta.ranking_mode}</Tag>
                      {searchState.response.meta.corrected_query ? (
                        <Tag color="blue">Исправлено: {searchState.response.meta.corrected_query}</Tag>
                      ) : null}
                      {searchState.response.meta.applied_synonyms.length ? (
                        <Tag color="purple">
                          Синонимы: {searchState.response.meta.applied_synonyms.slice(0, 2).join(', ')}
                        </Tag>
                      ) : null}
                    </>
                  ) : null}
                </SearchMetaGroup>
              </ContentHeader>

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
                                onChange={(page) => setCatalogPage(page)}
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
                              onChange={(page) => setCatalogPage(page)}
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
                      Сравнение построено как витрина каталога: карточки позиций сверху и таблица
                      параметров снизу. Подсвеченные строки помогают быстрее увидеть различия.
                    </CompareLead>
                    <CompareCards>
                      {visibleCompareItems.map((item) => {
                        const [from, to] = buildCardTone(item.item.id)
                        return (
                          <CompareSubjectCard key={item.id}>
                            <CompareSubjectVisual $from={from} $to={to}>
                              <ProductVisualLabel>{buildCardLabel(item.item.title)}</ProductVisualLabel>
                            </CompareSubjectVisual>
                            <CompareSubjectTitle>{item.item.title}</CompareSubjectTitle>
                            <CompareSubjectMeta>
                              <span>ID СТЕ: {item.item.id}</span>
                              <span>{item.item.category_name}</span>
                              <span>{item.item.supplier_name}</span>
                            </CompareSubjectMeta>
                            <ProductActions>
                              <Button
                                size="small"
                                onClick={() => navigate(buildProductPath(item.item.id, currentSessionId))}
                              >
                                Карточка
                              </Button>
                              <Button
                                size="small"
                                onClick={() =>
                                  comparisonMutation.mutate({
                                    steId: item.ste_id,
                                    active: true,
                                  })
                                }
                              >
                                Убрать
                              </Button>
                            </ProductActions>
                          </CompareSubjectCard>
                        )
                      })}
                      {Array.from({
                        length: Math.max(0, 4 - visibleCompareItems.length),
                      }).map((_, index) => (
                        <CompareSubjectCard key={`empty-card-${index}`}>
                          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Свободный слот" />
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
                    <CollectionEmptyState>
                      <Empty description="Добавьте товары в сравнение из результатов поиска." />
                      <CollectionEmptyText>
                        Сравнение собирается из карточек каталога. Откройте готовый сценарий,
                        отметьте 2-4 позиции и вернитесь сюда для просмотра различий.
                      </CollectionEmptyText>
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
                    </CollectionEmptyState>
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
                        onChange={(page) => setFavoritesPage(page)}
                        showSizeChanger={false}
                      />
                    </div>
                  ) : null}
                </>
              ) : (
                <div style={{ padding: 28 }}>
                  <CollectionEmptyState>
                    <Empty
                      description={
                        activeTab === 'favorites'
                          ? 'Пока нет избранных позиций.'
                          : 'Пока нет позиций в этом разделе.'
                      }
                    />
                    <CollectionEmptyText>
                      {activeTab === 'favorites'
                        ? 'Избранное помогает быстро собирать shortlist. Добавьте сюда позиции из каталога или из стартового сценария.'
                        : 'Раздел пока пуст. Откройте каталог и начните с готового сценария, чтобы наполнить его полезными позициями.'}
                    </CollectionEmptyText>
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
                  </CollectionEmptyState>
                </div>
              )}
            </SectionCard>

            <SectionCard>
              <ContentHeader>
                <div style={{ display: 'grid', gap: 4 }}>
                  <ContentTitle level={2}>Подсказки профиля</ContentTitle>
                  <ContentHint>
                    {hasProfileSignals || hasSearchHistory
                      ? 'Последние запросы и популярные категории для выбранного пользователя'
                      : 'Пока профиль пустой: здесь появятся ваши рабочие категории, запросы и быстрые возвраты'}
                  </ContentHint>
                </div>
              </ContentHeader>
              <div style={{ padding: 20, display: 'grid', gap: 16 }}>
                {hasProfileSignals || hasSearchHistory ? (
                  <>
                    <HintPanel>
                      <HintText>
                        {session.entry_mode === 'context'
                          ? 'Организационный контекст уже влияет на выдачу. Новые запросы и действия помогут быстрее превратить его в персональный профиль.'
                          : 'Этот блок собирает рабочий контекст пользователя: частые категории, повторяемые запросы и темы, к которым удобно возвращаться.'}
                      </HintText>
                      {session.entry_note ? <HintText>{session.entry_note}</HintText> : null}
                    </HintPanel>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {(profileQuery.data?.top_categories ?? []).slice(0, 8).map((item) => (
                        <Tag key={item} color="processing">
                          {item}
                        </Tag>
                      ))}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {(historyQuery.data?.items ?? []).slice(0, 6).map((item: SearchHistoryItem) => (
                        <Button
                          key={item.id}
                          onClick={() => {
                            setSearchValue(item.query)
                            void runSearch(item.query)
                          }}
                        >
                          {item.query}
                        </Button>
                      ))}
                    </div>
                  </>
                ) : (
                  <HintPanel>
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
                  </HintPanel>
                )}
              </div>
            </SectionCard>

            <SectionCard>
              <ContentHeader>
                <div style={{ display: 'grid', gap: 4 }}>
                  <ContentTitle level={2}>Последние действия</ContentTitle>
                  <ContentHint>
                    Живая лента недавних поисковых и закупочных действий пользователя
                  </ContentHint>
                </div>
                <Select
                  size="middle"
                  value={activityFilter}
                  style={{ minWidth: 180 }}
                  onChange={(value) => setActivityFilter(value as ActivityFilter)}
                  options={activityFilterOptions}
                />
              </ContentHeader>
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
                          <Tag color={getActivityColor(item.event_type)}>{item.event_type}</Tag>
                          {item.query ? <Tag>{item.query}</Tag> : null}
                          {item.ste_title ? <Tag color="geekblue">{item.ste_title}</Tag> : null}
                        </ActivityMeta>
                        <ActivityText>{item.description}</ActivityText>
                      </ActivityCard>
                    ))}
                  </ActivityTimeline>
                ) : (activityQuery.data?.items ?? []).length ? (
                  <HintPanel>
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
                  </HintPanel>
                ) : (
                  <HintPanel>
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
                  </HintPanel>
                )}
              </div>
            </SectionCard>
          </Content>
        </WorkspaceGrid>
      </Main>

    </PortalShell>
  )
}

export default HomePage
