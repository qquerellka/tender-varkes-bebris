import {
  AppstoreOutlined,
  BugOutlined,
  LogoutOutlined,
  RiseOutlined,
  ShoppingCartOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Avatar, Button } from 'antd'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import styled from 'styled-components'
import type { AuthSession } from '@shared/api/search'

type PortalNavItem = 'catalog' | 'cart' | 'supplier' | 'debug'

type PortalShellProps = {
  session: AuthSession
  activeNav: PortalNavItem
  children: ReactNode
  headerTools?: ReactNode
  onLogout?: () => void
}

const Screen = styled.div`
  min-height: 100vh;
  background:
    linear-gradient(180deg, #f5f6f8 0%, #eef2f5 26%, #f6f7f9 100%);
  color: #223047;
`

const TopBar = styled.header`
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: 1px solid #d9e0e8;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 8px 30px rgba(45, 67, 96, 0.08);
  backdrop-filter: blur(12px);
`

const TopBarInner = styled.div`
  display: flex;
  align-items: center;
  gap: 20px;
  width: min(1440px, calc(100% - 32px));
  margin: 0 auto;
  padding: 14px 0;

  @media (max-width: 960px) {
    width: min(100%, calc(100% - 20px));
    gap: 12px;
    padding: 12px 0;
  }
`

const Brand = styled.button`
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
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
  text-align: left;
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

const NavRail = styled.nav`
  display: flex;
  flex-wrap: wrap;
  gap: 10px;

  @media (max-width: 1180px) {
    display: none;
  }
`

const NavButton = styled(Button)<{ $active: boolean }>`
  &.ant-btn {
    height: 42px;
    border-radius: 0;
    border-color: ${({ $active }) => ($active ? '#2f4f84' : '#d9e0e8')};
    color: ${({ $active }) => ($active ? '#2f4f84' : '#5c6e84')};
    background: ${({ $active }) => ($active ? '#eef4ff' : '#ffffff')};
    font-weight: 700;
    box-shadow: none;
  }
`

const HeaderRight = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  margin-left: auto;
  min-width: 0;
`

const UserPanel = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
`

const UserMeta = styled.div`
  display: grid;
  gap: 2px;
  min-width: 0;
`

const UserName = styled.span`
  color: #3b4656;
  font-size: 15px;
  font-weight: 700;
  white-space: nowrap;
`

const UserHint = styled.span`
  color: #c26d2d;
  font-size: 12px;
  white-space: nowrap;
`

function PortalShell({ session, activeNav, children, headerTools, onLogout }: PortalShellProps) {
  const navigate = useNavigate()
  const roleLabel = session.role === 'supplier' ? 'Режим поставщика' : 'Режим заказчика'

  return (
    <Screen>
      <TopBar>
        <TopBarInner>
          <Brand type="button" onClick={() => navigate('/')}>
            <BrandMark />
            <BrandText>
              <BrandTitle>Портал</BrandTitle>
              <BrandSubtitle>Поставщиков</BrandSubtitle>
            </BrandText>
          </Brand>

          <NavRail aria-label="Основная навигация">
            <NavButton
              $active={activeNav === 'catalog'}
              icon={<AppstoreOutlined />}
              onClick={() => navigate('/')}
            >
              Каталог
            </NavButton>
            <NavButton
              $active={activeNav === 'cart'}
              icon={<ShoppingCartOutlined />}
              onClick={() => navigate('/cart')}
            >
              Черновик
            </NavButton>
            <NavButton
              $active={activeNav === 'debug'}
              icon={<BugOutlined />}
              onClick={() => navigate('/debug/telemetry')}
            >
              Telemetry
            </NavButton>
            {session.role === 'supplier' ? (
              <NavButton
                $active={activeNav === 'supplier'}
                icon={<RiseOutlined />}
                onClick={() => navigate('/supplier')}
              >
                Dashboard
              </NavButton>
            ) : null}
          </NavRail>

          <HeaderRight>
            {headerTools}
            <UserPanel>
              <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#dfe9f6', color: '#33578a' }} />
              <UserMeta>
                <UserName>{session.name}</UserName>
                <UserHint>
                  {roleLabel} · {session.organization_name}
                </UserHint>
              </UserMeta>
              {onLogout ? (
                <Button icon={<LogoutOutlined />} onClick={onLogout}>
                  Выйти
                </Button>
              ) : null}
            </UserPanel>
          </HeaderRight>
        </TopBarInner>
      </TopBar>

      {children}
    </Screen>
  )
}

export default PortalShell
