import {
  AppstoreOutlined,
  BarChartOutlined,
  CalendarOutlined,
  ContainerOutlined,
  DashboardOutlined,
  FileTextOutlined,
  FundOutlined,
  HeatMapOutlined,
  LineChartOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlayCircleOutlined,
  ReadOutlined,
  RobotOutlined,
  SettingOutlined,
  ShopOutlined,
  StarOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UserOutlined,
  VerticalAlignTopOutlined,
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Menu } from 'antd'
import { useEffect, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'
import { Brand } from '@/components/common/Brand'
import {
  SIDEBAR_COLLAPSED_WIDTH,
  SIDEBAR_DEFAULT_WIDTH,
  useSidebarStore,
} from '@/stores/sidebar'

type MenuItem = Required<MenuProps>['items'][number]

const REVIEW_MENU_ITEMS: MenuItem[] = [
  { key: '/workbench', icon: <AppstoreOutlined />, label: '工作台' },
  { key: '/review', icon: <BarChartOutlined />, label: '每日复盘' },
  { key: '/auction', icon: <ShopOutlined />, label: '集合竞价' },
  { key: '/calendar', icon: <CalendarOutlined />, label: '投资日历' },
  { key: '/capital-flow', icon: <FundOutlined />, label: '资金流向' },
  { key: '/telegraph', icon: <ThunderboltOutlined />, label: '财联社电报' },
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
  collapsed?: boolean
}

export function SidebarMenu({ onNavigate, collapsed = false }: SidebarMenuProps) {
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
    { key: '/watchlist', icon: <StarOutlined />, label: '自选股管理' },
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
      <div
        className={`h-14 flex items-center border-b border-gray-800 shrink-0 ${
          collapsed ? 'justify-center px-0' : 'px-4'
        }`}
      >
        {collapsed ? (
          <SidebarIconButton title="展开侧边栏" onClick={() => useSidebarStore.getState().toggleCollapsed()}>
            <MenuUnfoldOutlined />
          </SidebarIconButton>
        ) : (
          <>
            <div className="flex-1 min-w-0">
              <Brand showVersion />
            </div>
            <SidebarIconButton title="收起侧边栏" onClick={() => useSidebarStore.getState().toggleCollapsed()}>
              <MenuFoldOutlined />
            </SidebarIconButton>
          </>
        )}
      </div>
      <Menu
        theme="dark"
        mode="inline"
        inlineCollapsed={collapsed}
        selectedKeys={[resolveSelectedKey(location.pathname, leafKeys(items))]}
        openKeys={collapsed ? [] : openKeys}
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
      {user && !collapsed && (
        <div className="p-4 border-t border-gray-800 text-sm text-gray-400 shrink-0">
          {user.email}
        </div>
      )}
    </div>
  )
}

function SidebarIconButton({
  title,
  onClick,
  children,
}: {
  title: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="flex items-center justify-center w-7 h-7 shrink-0 rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
    >
      {children}
    </button>
  )
}

export function Sidebar() {
  const collapsed = useSidebarStore((s) => s.collapsed)
  const width = useSidebarStore((s) => s.width)
  const setWidth = useSidebarStore((s) => s.setWidth)

  // 右缘拖拽调宽：sidebar 贴视口左缘，宽度即鼠标 clientX；双击复位
  const startResize = (e: ReactMouseEvent) => {
    e.preventDefault()
    const onMove = (ev: MouseEvent) => setWidth(ev.clientX)
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <aside
      className="relative hidden md:flex shrink-0 border-r border-gray-800 bg-[#111318] flex-col"
      style={{ width: collapsed ? SIDEBAR_COLLAPSED_WIDTH : width }}
    >
      <SidebarMenu collapsed={collapsed} />
      {!collapsed && (
        <div
          title="拖拽调整宽度 · 双击复位"
          onMouseDown={startResize}
          onDoubleClick={() => setWidth(SIDEBAR_DEFAULT_WIDTH)}
          className="absolute top-0 right-0 z-10 h-full w-[3px] cursor-col-resize transition-colors hover:bg-[rgba(94,106,210,0.5)]"
        />
      )}
    </aside>
  )
}
