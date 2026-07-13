import { BarChartOutlined, FundOutlined, HeatMapOutlined, LineChartOutlined, ReadOutlined, SettingOutlined, ShopOutlined } from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Menu } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

type MenuItem = Required<MenuProps>['items'][number]

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, isAdmin } = useAuthStore()

  const items: MenuItem[] = [
    {
      key: '/',
      icon: <BarChartOutlined />,
      label: '仪表盘',
    },
    {
      key: '/chain',
      icon: <HeatMapOutlined />,
      label: '产业链分析',
    },
    {
      key: '/hotspot',
      icon: <LineChartOutlined />,
      label: '热点追踪',
    },
    {
      key: '/capital-flow',
      icon: <FundOutlined />,
      label: '资金流向',
    },
    {
      key: '/auction',
      icon: <ShopOutlined />,
      label: '集合竞价',
    },
    {
      key: '/research',
      icon: <ReadOutlined />,
      label: '研报中心',
    },
    ...(isAdmin
      ? [
          {
            key: '/admin',
            icon: <SettingOutlined />,
            label: '后台管理',
          },
        ]
      : []),
  ]

  const selectedKey = items.find((item) => item?.key && location.pathname.startsWith(String(item.key)))?.key ?? '/'

  return (
    <aside className="w-56 border-r border-gray-800 bg-[#111318] flex flex-col">
      <div className="h-14 flex items-center px-4 border-b border-gray-800">
        <span className="text-lg font-bold text-white">AI Invest</span>
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[String(selectedKey)]}
        items={items}
        onClick={({ key }) => navigate(key)}
        className="!bg-transparent flex-1"
        style={{ borderRight: 0 }}
      />
      {user && (
        <div className="p-4 border-t border-gray-800 text-sm text-gray-400">
          {user.email}
        </div>
      )}
    </aside>
  )
}
