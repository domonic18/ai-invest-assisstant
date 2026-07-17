import {
  BarChartOutlined,
  ContainerOutlined,
  DashboardOutlined,
  FileTextOutlined,
  FundOutlined,
  HeatMapOutlined,
  LineChartOutlined,
  PlayCircleOutlined,
  ReadOutlined,
  RobotOutlined,
  SettingOutlined,
  ShopOutlined,
  TeamOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Menu } from 'antd'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'

type MenuItem = Required<MenuProps>['items'][number]

const MAIN_MENU_ITEMS: MenuItem[] = [
  { key: '/', icon: <BarChartOutlined />, label: '仪表盘' },
  { key: '/chain', icon: <HeatMapOutlined />, label: '产业链分析' },
  { key: '/hotspot', icon: <LineChartOutlined />, label: '热点追踪' },
  { key: '/capital-flow', icon: <FundOutlined />, label: '资金流向' },
  { key: '/auction', icon: <ShopOutlined />, label: '集合竞价' },
  { key: '/research', icon: <ReadOutlined />, label: '研报中心' },
]

const ADMIN_MENU_ITEMS: MenuItem[] = [
  { key: '/admin', icon: <DashboardOutlined />, label: '管理总览' },
  { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
  { key: '/admin/stocks', icon: <BarChartOutlined />, label: '股票管理' },
  { key: '/admin/reports', icon: <FileTextOutlined />, label: '研报管理' },
  { key: '/admin/news', icon: <ReadOutlined />, label: '资讯管理' },
  { key: '/admin/tasks', icon: <ContainerOutlined />, label: '任务管理' },
  { key: '/admin/llm-configs', icon: <RobotOutlined />, label: 'LLM 配置' },
  { key: '/admin/collector-channels', icon: <SettingOutlined />, label: '采集渠道' },
  { key: '/admin/collector', icon: <PlayCircleOutlined />, label: '采集任务' },
]

const ADMIN_GROUP_KEY = 'admin-group'

function leafKeys(items: MenuItem[]): string[] {
  return items.flatMap((item) => (item && 'key' in item ? [String(item.key)] : []))
}

const ALL_LEAF_KEYS = [...leafKeys(MAIN_MENU_ITEMS), ...leafKeys(ADMIN_MENU_ITEMS)]

function resolveSelectedKey(pathname: string): string {
  const matched = ALL_LEAF_KEYS.filter((key) =>
    key === '/' ? pathname === '/' : pathname.startsWith(key),
  )
  return matched.sort((a, b) => b.length - a.length)[0] ?? '/'
}

export function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, isAdmin } = useAuthStore()

  const isAdminPath = location.pathname.startsWith('/admin')
  const [openKeys, setOpenKeys] = useState<string[]>(isAdminPath ? [ADMIN_GROUP_KEY] : [])

  useEffect(() => {
    if (isAdminPath) {
      setOpenKeys((prev) => (prev.includes(ADMIN_GROUP_KEY) ? prev : [...prev, ADMIN_GROUP_KEY]))
    }
  }, [isAdminPath])

  const items: MenuItem[] = [
    ...MAIN_MENU_ITEMS,
    ...(isAdmin
      ? [
          {
            key: ADMIN_GROUP_KEY,
            icon: <SettingOutlined />,
            label: '后台管理',
            children: ADMIN_MENU_ITEMS,
          },
        ]
      : []),
  ]

  return (
    <aside className="w-56 border-r border-gray-800 bg-[#111318] flex flex-col">
      <div className="h-14 flex items-center px-4 border-b border-gray-800">
        <span className="text-lg font-bold text-white">AI Invest</span>
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[resolveSelectedKey(location.pathname)]}
        openKeys={openKeys}
        onOpenChange={(keys) => setOpenKeys(keys as string[])}
        items={items}
        onClick={({ key }) => {
          if (key.startsWith('/')) navigate(key)
        }}
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
