import { LogoutOutlined, MenuOutlined, MessageOutlined, SettingOutlined, StarOutlined, UserOutlined } from '@ant-design/icons'
import { Avatar, Button, Dropdown, Space, Tooltip } from 'antd'
import type { MenuProps } from 'antd'
import { Link, useNavigate } from 'react-router-dom'

import { useAssistantStore } from '@/stores/assistant'
import { useAuthStore } from '@/stores/auth'

import { StockSearch } from './StockSearch'

interface HeaderProps {
  /** 移动端打开导航抽屉。 */
  onMenuClick?: () => void
}

export function Header({ onMenuClick }: HeaderProps) {
  const navigate = useNavigate()
  const { user, isAdmin, logout } = useAuthStore()
  const openPanel = useAssistantStore((state) => state.openPanel)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const items: MenuProps['items'] = [
    {
      key: 'profile',
      type: 'group',
      label: (
        <div className="flex items-center gap-2 py-1">
          <Avatar size="small" icon={<UserOutlined />} />
          <div className="flex flex-col leading-tight">
            <span className="text-sm text-gray-200">{user?.username}</span>
            <span className="text-xs text-gray-500">{user?.email}</span>
          </div>
        </div>
      ),
    },
    { type: 'divider' },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">个人设置</Link>,
    },
    ...(isAdmin
      ? [
          {
            key: 'admin',
            icon: <SettingOutlined />,
            label: <Link to="/admin">后台管理</Link>,
          },
        ]
      : []),
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      danger: true,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  return (
    <header className="h-14 border-b border-gray-800 flex items-center px-3 md:px-6 justify-between bg-[#111318]">
      <div className="flex items-center gap-3 min-w-0">
        <Button
          type="text"
          icon={<MenuOutlined />}
          onClick={onMenuClick}
          className="md:!hidden text-gray-300"
          aria-label="打开导航菜单"
        />
        <div className="hidden md:block">
          <StockSearch />
        </div>
      </div>
      <Space size={4}>
        <Tooltip title="我的自选">
          <Button
            type="text"
            icon={<StarOutlined />}
            onClick={() => navigate('/watchlist')}
            className="text-gray-300"
            aria-label="我的自选"
          />
        </Tooltip>
        <Tooltip title="AI 助手">
          <Button
            type="text"
            icon={<MessageOutlined />}
            onClick={() => openPanel()}
            className="text-gray-300"
            aria-label="AI 助手"
          />
        </Tooltip>
        {user ? (
          <Dropdown menu={{ items }} placement="bottomRight">
            <Button type="text" className="text-gray-300">
              <Space>
                <Avatar size="small" icon={<UserOutlined />} />
                {user.username}
              </Space>
            </Button>
          </Dropdown>
        ) : (
          <Link to="/login">登录</Link>
        )}
      </Space>
    </header>
  )
}
