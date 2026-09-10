import {
  AppstoreOutlined,
  BarChartOutlined,
  BlockOutlined,
  CalendarOutlined,
  CloudServerOutlined,
  DashboardOutlined,
  FileTextOutlined,
  FileDoneOutlined,
  FundOutlined,
  GlobalOutlined,
  HeatMapOutlined,
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
} from '@ant-design/icons'
import type { MenuProps } from 'antd'
import { Menu } from 'antd'
import { useEffect, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuthStore } from '@/stores/auth'
import { Brand } from '@/components/common/Brand'
import { SidebarReviewStatus } from '@/components/layout/SidebarReviewStatus'
import {
  SIDEBAR_COLLAPSED_WIDTH,
  SIDEBAR_DEFAULT_WIDTH,
  useSidebarStore,
} from '@/stores/sidebar'

type MenuItem = Required<MenuProps>['items'][number]

// 导航信息架构见需求 4.4.0：监测 → 资讯 → 分析 → 设置。
// 资讯中心 /news 与异动双页（迭代 3/5）上线后再挂出；
// 个股监测经顶部搜索进入（/stock/:code 无默认标的，不设静态导航项）。
const MONITOR_MENU_ITEMS: MenuItem[] = [
  { key: '/macro-monitor', icon: <GlobalOutlined />, label: '宏观指数' },
  { key: '/capital-flow', icon: <FundOutlined />, label: '板块监测' },
  { key: '/auction-review', icon: <ShopOutlined />, label: '集合竞价' },
]

const NEWS_MENU_ITEMS: MenuItem[] = [
  // 迭代 3：电报视图迁入资讯中心 /news（渠道监控 + AI 分级 + 三视图）
  { key: '/news', icon: <ThunderboltOutlined />, label: '资讯中心' },
  { key: '/calendar', icon: <CalendarOutlined />, label: '投资日历' },
]

const ANALYSIS_MENU_ITEMS: MenuItem[] = [
  { key: '/review', icon: <BarChartOutlined />, label: '每日复盘' },
  { key: '/chain', icon: <HeatMapOutlined />, label: '产业图谱' },
]

const ADMIN_MENU_ITEMS: MenuItem[] = [
  { key: '/admin', icon: <DashboardOutlined />, label: '管理总览' },
  { key: '/admin/users', icon: <TeamOutlined />, label: '用户管理' },
  { key: '/admin/stocks', icon: <BarChartOutlined />, label: '股票管理' },
  { key: '/admin/reports', icon: <FileTextOutlined />, label: '报告管理' },
  { key: '/admin/news', icon: <ReadOutlined />, label: '资讯管理' },
  { key: '/admin/llm-configs', icon: <RobotOutlined />, label: 'LLM 配置' },
  { key: '/admin/proxy-configs', icon: <CloudServerOutlined />, label: '代理配置' },
  { key: '/admin/ai-results', icon: <FileDoneOutlined />, label: '分析结果' },
  { key: '/admin/collector', icon: <PlayCircleOutlined />, label: '采集管理' },
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
  const { isAdmin } = useAuthStore()

  const isAdminPath = location.pathname.startsWith('/admin')
  const [openKeys, setOpenKeys] = useState<string[]>(isAdminPath ? [ADMIN_GROUP_KEY] : [])

  useEffect(() => {
    if (isAdminPath) {
      setOpenKeys((prev) => (prev.includes(ADMIN_GROUP_KEY) ? prev : [...prev, ADMIN_GROUP_KEY]))
    }
  }, [isAdminPath])

  const settingsChildren: MenuItem[] = [
    { key: '/settings', icon: <UserOutlined />, label: '个人设置' },
    { key: '/skills', icon: <BlockOutlined />, label: '技能广场' },
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
    { key: '/workbench', icon: <AppstoreOutlined />, label: '工作台' },
    { key: '/watchlist', icon: <StarOutlined />, label: '我的自选' },
    { type: 'group', key: 'group-monitor', label: '监测', children: MONITOR_MENU_ITEMS },
    { type: 'group', key: 'group-news', label: '资讯', children: NEWS_MENU_ITEMS },
    { type: 'group', key: 'group-analysis', label: '分析', children: ANALYSIS_MENU_ITEMS },
    { type: 'group', key: 'group-settings', label: '设置', children: settingsChildren },
  ]

  // 折叠态下 AntD 的 type:'group' 项不可交互（点击分组图标无响应），
  // 拍平为叶子项让每个图标可点；后台管理是普通子菜单，保留为弹出菜单。
  const displayItems: MenuItem[] = collapsed
    ? items.flatMap((item) =>
        item && 'type' in item && item.type === 'group'
          ? (item.children as MenuItem[])
          : [item],
      )
    : items

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
        items={displayItems}
        onClick={({ key }) => {
          if (key.startsWith('/')) {
            navigate(key)
            onNavigate?.()
          }
        }}
        className="!bg-transparent flex-1 overflow-y-auto"
        style={{ borderRight: 0 }}
      />
      {!collapsed && <SidebarReviewStatus />}
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
