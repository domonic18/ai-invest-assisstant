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
  UserOutlined,
  VerticalAlignTopOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Menu } from 'antd'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'
import { Brand } from '@/components/common/Brand'

type MenuItem = Required<MenuProps>['items'][number]

const REVIEW_MENU_ITEMS: MenuItem[] = [
  { key: '/', icon: <BarChartOutlined />, label: '每日复盘' },
  { key: '/auction', icon: <ShopOutlined />, label: '集合竞价' },
  { key: '/capital-flow', icon: <FundOutlined />, label: '资金流向' },
]

const ANALYSIS_MENU_ITEMS: MenuItem[] = [
  { key: '/chain', icon: <HeatMapOutlined />, label: '产业链分析' },
  { key: '/hotspot', icon: <LineChartOutlined />, label: '热点追踪' },
  { key: '/financial-reports', icon: <FileTextOutlined />, label: '财报中心' },
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
  { key: '/admin/tracked-indexes', icon: <VerticalAlignTopOutlined />, label: '跟踪指数' },
  { key: '/admin/collector-channels', icon: <SettingOutlined />, label: '采集渠道' },
  { key: '/admin/collector', icon: <PlayCircleOutlined />, label: '采集任务' },
]

const ADMIN_GROUP_KEY = 'admin-group'

function leafKeys(items: MenuItem[]): string[] {
  return items.flatMap((item) => {
    if (!item || !('key' in item)) return []
    const children =
      'children' in item && Array.isArray(item.children)
        ? leafKeys(item.children as MenuItem[])
        : []
    return [String(item.key), ...children]
  })
}

function resolveSelectedKey(pathname: string, keys: string[]): string {
  const matched = keys
    .filter((key) => key.startsWith('/'))
    .filter((key) => (key === '/' ? pathname === '/' : pathname.startsWith(key)))
  return matched.sort((a, b) => b.length - a.length)[0] ?? '/'
}

interface SidebarMenuProps {
  /** 导航后回调（移动端抽屉场景用于关闭抽屉）。 */
  onNavigate?: () => void
}

export function SidebarMenu({ onNavigate }: SidebarMenuProps) {
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

  const settingsChildren: MenuItem[] = [
    { key: '/settings', icon: <UserOutlined />, label: '个人设置' },
    ...(isAdmin
      ? [
          {
            key: ADMIN_GROUP_KEY,
            icon: <SettingOutlined />,
            label: '后台管理',
            children: ADMIN_MENU_ITEMS,
          } as MenuItem,
        ]
      : []),
  ]

  const items: MenuItem[] = [
    { type: 'group', key: 'group-review', label: '复盘', children: REVIEW_MENU_ITEMS },
    { type: 'group', key: 'group-analysis', label: '分析', children: ANALYSIS_MENU_ITEMS },
    { type: 'group', key: 'group-settings', label: '设置', children: settingsChildren },
  ]

  return (
    <div className="h-full flex flex-col bg-[#111318]">
      <div className="h-14 flex items-center px-4 border-b border-gray-800 shrink-0">
        <Brand showVersion />
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[resolveSelectedKey(location.pathname, leafKeys(items))]}
        openKeys={openKeys}
        onOpenChange={(keys) => setOpenKeys(keys as string[])}
        items={items}
        onClick={({ key }) => {
          if (key.startsWith('/')) {
            navigate(key)
            onNavigate?.()
          }
        }}
        className="!bg-transparent flex-1 overflow-y-auto"
        style={{ borderRight: 0 }}
      />
      {user && (
        <div className="p-4 border-t border-gray-800 text-sm text-gray-400 shrink-0">
          {user.email}
        </div>
      )}
    </div>
  )
}

export function Sidebar() {
  return (
    <aside className="hidden md:flex w-56 border-r border-gray-800 bg-[#111318] flex-col">
      <SidebarMenu />
    </aside>
  )
}
