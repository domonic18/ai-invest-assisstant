import { Drawer } from 'antd'
import { useState } from 'react'
import { Outlet } from 'react-router-dom'

import { AssistantFab, AssistantPanel } from '@/components/assistant/AssistantPanel'

import { Header } from './Header'
import { MobileTabBar } from './MobileTabBar'
import { Sidebar, SidebarMenu } from './Sidebar'

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const closeMenu = () => setMenuOpen(false)

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
      <AssistantFab />
      <AssistantPanel />
    </div>
  )
}
