import {
  BarChartOutlined,
  FundOutlined,
  LogoutOutlined,
  SettingOutlined,
  ShopOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { Avatar, Drawer } from 'antd'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

const TAB_ITEMS = [
  { key: '/', icon: <BarChartOutlined />, label: '复盘' },
  { key: '/auction', icon: <ShopOutlined />, label: '竞价' },
  { key: '/capital-flow', icon: <FundOutlined />, label: '资金' },
]

export function MobileTabBar() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, isAdmin, logout } = useAuthStore()
  const [profileOpen, setProfileOpen] = useState(false)

  const itemClass = (active: boolean) =>
    `flex flex-1 flex-col items-center justify-center gap-0.5 text-[10px] min-h-[48px] ${
      active ? 'text-[#5e6ad2]' : 'text-gray-400'
    }`

  const go = (path: string) => {
    setProfileOpen(false)
    navigate(path)
  }

  const handleLogout = () => {
    setProfileOpen(false)
    logout()
    navigate('/login')
  }

  const actionClass =
    'flex items-center gap-3 px-4 py-3 text-sm text-gray-200 active:bg-[#1c1f26] w-full text-left'

  return (
    <>
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 flex border-t border-gray-800 bg-[#111318] pb-[env(safe-area-inset-bottom)]">
        {TAB_ITEMS.map((item) => (
          <Link key={item.key} to={item.key} className={itemClass(pathname === item.key)}>
            <span className="text-base">{item.icon}</span>
            {item.label}
          </Link>
        ))}
        <button
          type="button"
          onClick={() => setProfileOpen(true)}
          className={itemClass(pathname === '/settings')}
        >
          <span className="text-base">
            <UserOutlined />
          </span>
          我的
        </button>
      </nav>

      <Drawer
        placement="bottom"
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        height="auto"
        closable={false}
        styles={{ body: { padding: '8px 0 calc(8px + env(safe-area-inset-bottom))' } }}
      >
        {user && (
          <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 mb-1">
            <Avatar icon={<UserOutlined />} />
            <div>
              <div className="text-sm font-medium text-gray-100">{user.username}</div>
              <div className="text-xs text-gray-500">{user.email}</div>
            </div>
          </div>
        )}
        <button type="button" className={actionClass} onClick={() => go('/settings')}>
          <SettingOutlined className="text-gray-400" />
          个人设置
        </button>
        {isAdmin && (
          <button type="button" className={actionClass} onClick={() => go('/admin')}>
            <SettingOutlined className="text-gray-400" />
            后台管理
          </button>
        )}
        <button type="button" className={`${actionClass} !text-red-400`} onClick={handleLogout}>
          <LogoutOutlined />
          退出登录
        </button>
      </Drawer>
    </>
  )
}
