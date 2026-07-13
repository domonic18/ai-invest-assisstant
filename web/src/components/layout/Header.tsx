import { LogoutOutlined, SettingOutlined, UserOutlined } from '@ant-design/icons'
import { Avatar, Button, Dropdown, Space, Typography } from 'antd'
import { Link, useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

export function Header() {
  const navigate = useNavigate()
  const { user, isAdmin, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const items = [
    ...(isAdmin
      ? [
          {
            key: 'admin',
            icon: <SettingOutlined />,
            label: <Link to="/admin">后台管理</Link>,
          },
        ]
      : []),
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: <Link to="/settings">设置</Link>,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ]

  return (
    <header className="h-14 border-b border-gray-800 flex items-center px-6 justify-between bg-[#111318]">
      <Typography.Text className="text-lg font-semibold">AI Invest Assistant</Typography.Text>
      <Space>
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
