import type { ChangeEvent, FormEvent, PropsWithChildren } from 'react'
import { SearchOutlined } from '@ant-design/icons'
import { AutoComplete, Button, Checkbox, Input, Layout, Select, Space, Tag, Typography } from 'antd'
import type { AutoCompleteProps } from 'antd'
import styled from 'styled-components'
import type { DemoUser } from '@features/search-catalog/model/demo-users'
import type { CatalogCategory, CatalogSupplier } from '@shared/api/search'
import { searchScopeOptions, type SearchScope } from './layout.constants'

const { Header, Content } = Layout

type AutocompleteOption = NonNullable<AutoCompleteProps['options']>[number]

type PortalLayoutProps = PropsWithChildren<{
  demoUsers: DemoUser[]
  activeUserId: string
  activeUserLabel?: string | null
  categories: CatalogCategory[]
  suppliers: CatalogSupplier[]
  selectedCategoryId?: string
  selectedSupplierId?: string
  personalizationSummary?: string[]
  searchValue: string
  searchScope: SearchScope
  strictMatch: boolean
  isSearching?: boolean
  scopeHint?: string | null
  suggestionsHint?: string | null
  autocompleteOptions?: AutocompleteOption[]
  onActiveUserChange: (value: string) => void
  onCategoryChange: (value?: string) => void
  onSearchValueChange: (value: string) => void
  onSuggestionSelect?: (value: string) => void
  onScopeChange: (value: SearchScope) => void
  onSupplierChange: (value?: string) => void
  onResetFilters: () => void
  onStrictMatchChange: (value: boolean) => void
  onSubmit: () => void
}>

const Shell = styled(Layout)`
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.72) 0 106px, transparent 106px),
    transparent;
`

const PortalHeader = styled(Header)`
  display: flex;
  align-items: center;
  height: 106px;
  padding: 18px 32px 16px;
  border-bottom: 1px solid #d9dfe6;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 8px 20px rgba(57, 70, 87, 0.08);
  backdrop-filter: blur(10px);

  @media (max-width: 992px) {
    height: auto;
    padding-inline: 16px;
  }
`

const Toolbar = styled.form`
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: min(1190px, 100%);
  margin: 0 auto;
`

const SearchCompact = styled(Space.Compact)`
  display: flex;
  width: 100%;

  @media (max-width: 992px) {
    display: block;
    width: 100%;
  }
`

const CategorySelect = styled(Select<SearchScope>)`
  width: 230px;

  .ant-select-selector {
    border-radius: 0 !important;
    border-top-left-radius: 4px !important;
    border-bottom-left-radius: 4px !important;
    border-right: 0 !important;
  }

  @media (max-width: 992px) {
    width: 100%;
    margin-bottom: 10px;

    .ant-select-selector {
      border-radius: 4px !important;
      border-right-width: 1px !important;
    }
  }
`

const SearchAutocomplete = styled(AutoComplete)`
  flex: 1;

  .ant-select-selector {
    padding: 0 !important;
    border-radius: 0 !important;
    border-right: 0 !important;
    box-shadow: none !important;
  }

  @media (max-width: 992px) {
    width: 100%;
  }
`

const SearchInput = styled(Input)`
  &.ant-input {
    height: 44px;
    border: 0;
    border-radius: 0 !important;
    box-shadow: none !important;
  }

  @media (max-width: 992px) {
    &.ant-input {
      border-radius: 4px !important;
    }
  }
`

const SearchButton = styled(Button)`
  &.ant-btn {
    width: 44px;
    height: 44px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    box-shadow: none;
  }

  @media (max-width: 992px) {
    &.ant-btn {
      width: 100%;
      margin-top: 10px;
      border-radius: 4px;
    }
  }
`

const SecondaryRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 24px;

  @media (max-width: 992px) {
    flex-direction: column;
    align-items: flex-start;
  }
`

const SecondaryControls = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
`

const UserSelect = styled(Select<string>)`
  width: 360px;

  @media (max-width: 992px) {
    width: 100%;
  }
`

const FilterSelect = styled(Select<string>)`
  width: 220px;

  @media (max-width: 992px) {
    width: 100%;
  }
`

const StrictCheckbox = styled(Checkbox)`
  &.ant-checkbox-wrapper {
    color: #4b5563;
    font-size: 15px;
  }
`

const ScopeHint = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`

const HintText = styled(Typography.Text)`
  color: #5c6978;
  font-size: 13px;
`

const PortalContent = styled(Content)`
  padding: 28px 32px 40px;
  background: transparent;

  @media (max-width: 992px) {
    padding-inline: 16px;
  }
`

const SuggestionFooter = styled.button`
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 14px 16px 10px;
  border: 0;
  border-top: 1px solid #e1e7ef;
  color: #2d5b90;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  text-align: left;
  background: #fff;
  cursor: pointer;

  &:hover {
    background: #f5f9ff;
  }
`

export function PortalLayout({
  children,
  demoUsers,
  activeUserId,
  activeUserLabel,
  categories,
  suppliers,
  selectedCategoryId,
  selectedSupplierId,
  personalizationSummary = [],
  searchValue,
  searchScope,
  strictMatch,
  isSearching = false,
  scopeHint,
  suggestionsHint,
  autocompleteOptions = [],
  onActiveUserChange,
  onCategoryChange,
  onSearchValueChange,
  onSuggestionSelect,
  onScopeChange,
  onSupplierChange,
  onResetFilters,
  onStrictMatchChange,
  onSubmit,
}: PortalLayoutProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit()
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    onSearchValueChange(event.target.value)
  }

  const handleSuggestionSelect = (value: unknown) => {
    if (typeof value === 'string') {
      onSuggestionSelect?.(value)
    }
  }

  return (
    <Shell>
      <PortalHeader>
        <Toolbar onSubmit={handleSubmit}>
          <SearchCompact block>
            <CategorySelect
              value={searchScope}
              options={[...searchScopeOptions]}
              onChange={onScopeChange}
            />
            <SearchAutocomplete
              value={searchValue}
              options={autocompleteOptions}
              popupClassName="search-suggestions-popup"
              popupRender={(originNode) => (
                <div>
                  {originNode}
                  {searchValue.trim() ? (
                    <SuggestionFooter
                      type="button"
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={onSubmit}
                    >
                      Открыть все найденные
                    </SuggestionFooter>
                  ) : null}
                </div>
              )}
              onSelect={handleSuggestionSelect}
            >
              <SearchInput
                allowClear
                value={searchValue}
                onChange={handleInputChange}
                placeholder="Введите название категории, товара или ID СТЕ"
              />
            </SearchAutocomplete>
            <SearchButton
              aria-label="Искать"
              type="primary"
              htmlType="submit"
              loading={isSearching}
              icon={<SearchOutlined />}
            />
          </SearchCompact>

          <SecondaryRow>
            <SecondaryControls>
              <UserSelect
                value={activeUserId}
                options={demoUsers.map((user) => ({
                  value: user.id,
                  label: `${user.name} · ${user.persona}`,
                }))}
                onChange={onActiveUserChange}
              />

              <FilterSelect
                allowClear
                placeholder="Все категории"
                value={selectedCategoryId}
                options={categories.map((category) => ({
                  value: category.id,
                  label: category.name,
                }))}
                onChange={(value) => onCategoryChange(value)}
              />

              <FilterSelect
                allowClear
                placeholder="Все поставщики"
                value={selectedSupplierId}
                options={suppliers.map((supplier) => ({
                  value: supplier.id,
                  label: supplier.name,
                }))}
                onChange={(value) => onSupplierChange(value)}
              />

              <StrictCheckbox
                checked={strictMatch}
                onChange={(event) => onStrictMatchChange(event.target.checked)}
              >
                Строгое соответствие
              </StrictCheckbox>

              <Button onClick={onResetFilters}>Сбросить фильтры</Button>
            </SecondaryControls>

            {activeUserLabel || scopeHint || suggestionsHint || personalizationSummary.length ? (
              <ScopeHint>
                {activeUserLabel ? <Tag color="geekblue">{activeUserLabel}</Tag> : null}
                {personalizationSummary.map((category) => (
                  <Tag key={category} color="gold">
                    {category}
                  </Tag>
                ))}
                {suggestionsHint ? <Tag color="processing">{suggestionsHint}</Tag> : null}
                {scopeHint ? (
                  <>
                    <Tag color="blue">Демо</Tag>
                    <HintText>{scopeHint}</HintText>
                  </>
                ) : null}
              </ScopeHint>
            ) : null}
          </SecondaryRow>
        </Toolbar>
      </PortalHeader>
      <PortalContent>{children}</PortalContent>
    </Shell>
  )
}

export default PortalLayout
