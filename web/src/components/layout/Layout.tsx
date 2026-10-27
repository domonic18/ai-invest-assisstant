import { Drawer } from 'antd'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Outlet, ScrollRestoration } from 'react-router-dom'

import { canAccessFeature } from '@ai-invest/shared'

import { useAuthStore } from '@/stores/auth'

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
  const user = useAuthStore((s) => s.user)
  const canAssistant = canAccessFeature(user, 'assistant')
  useIdlePrefetch()

  return (
    <div className="flex min-h-dvh bg-[#0c0e12] text-gray-100">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header onMenuClick={() => setMenuOpen(true)} />
        <main className="p-3 pb-20 md:p-6">
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
        <SidebarMenu onNavigate={closeMenu} showToolEntries />
      </Drawer>
      {canAssistant && (
        <Suspense fallback={null}>
          <AssistantFab />
          <AssistantPanel />
        </Suspense>
      )}
      <ScrollRestoration />
    </div>
  )
}
