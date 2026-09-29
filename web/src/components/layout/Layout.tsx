import { Drawer } from 'antd'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'

import { Header } from './Header'
import { MobileTabBar } from './MobileTabBar'
import { Sidebar, SidebarMenu } from './Sidebar'

// assistant 生态（@assistant-ui + langgraph-sdk + markdown 管线）体积大且首屏
// 用不到，懒加载使其依赖整体移出 index chunk；空闲时预取，点击时零等待
const AssistantFab = lazy(() =>
  import('@/components/assistant/AssistantPanel').then((m) => ({ default: m.AssistantFab })),
)
const AssistantPanel = lazy(() =>
  import('@/components/assistant/AssistantPanel').then((m) => ({ default: m.AssistantPanel })),
)

function useIdlePrefetch() {
  useEffect(() => {
    const id = window.requestIdleCallback(() => void import('@/components/assistant/AssistantPanel'), { timeout: 5000 })
    return () => window.cancelIdleCallback(id)
  }, [])
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)
  useIdlePrefetch()

  return (
    <div className="flex h-screen bg-[#0c0e12] text-gray-100">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header onMenuClick={() => setMenuOpen(true)} />
        <main className="flex-1 overflow-auto p-3 pb-20 md:p-6">
          <Outlet />
        </main>
        <MobileTabBar />
      </div>
      <Drawer
        placement="left"
        open={menuOpen}
        onClose={closeMenu}
        width={240}
        closable={false}
        styles={{ body: { padding: 0 } }}
      >
        <SidebarMenu onNavigate={closeMenu} />
      </Drawer>
      <Suspense fallback={null}>
        <AssistantFab />
        <AssistantPanel />
      </Suspense>
    </div>
  )
}
