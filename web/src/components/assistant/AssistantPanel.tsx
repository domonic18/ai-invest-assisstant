import { Drawer, Tooltip } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useAgentOverview } from '@/hooks/useTradingAgent'
import { useAssistantStore } from '@/stores/assistant'
import { useAuthStore } from '@/stores/auth'

import { useIsNarrowScreen } from '@/hooks/useIsNarrowScreen'

import { useAssistantSessions } from './hooks/useAssistantSessions'
import { AssistantHeader } from './AssistantHeader'
import { AssistantSidebar } from './AssistantSidebar'
import { AssistantThread } from './AssistantThread'
import { AssistantErrorBoundary } from './AssistantErrorBoundary'
import { AssistantRuntimeProvider } from './AssistantRuntimeProvider'
import { ASSISTANT_AVATAR } from './ui/agentAvatars'
import { TodoListBar } from './ui/TodoListBar'
import {
  clamp,
  DEFAULT_DRAWER_WIDTH,
  DEFAULT_SIDEBAR_WIDTH,
  DRAWER_STORAGE_KEY,
  FAB_COLLAPSED_KEY,
  MAX_DRAWER_WIDTH,
  MAX_SIDEBAR_WIDTH,
  MIN_DRAWER_WIDTH,
  MIN_SIDEBAR_WIDTH,
  readStoredWidth,
  SIDEBAR_STORAGE_KEY,
} from './utils'

import './AssistantFab.css'

export function AssistantPanel() {
  const open = useAssistantStore((state) => state.open)
  const closePanel = useAssistantStore((state) => state.closePanel)
  const threadId = useAssistantStore((state) => state.threadId)
  const switchThread = useAssistantStore((state) => state.switchThread)
  const chatAgentType = useAssistantStore((state) => state.chatAgentType)
  const setChatAgent = useAssistantStore((state) => state.setChatAgent)
  const todos = useAssistantStore((state) => state.todos)
  const isAdmin = useAuthStore((state) => state.isAdmin)

  // 会话列表随对话对象切换（queryKey 含 agentType，切 key 自带 Loading 重取）
  const { sessions, isLoading, deleteSessionById, refresh } = useAssistantSessions({
    agentType: chatAgentType,
    enabled: open,
  })
  const { data: overview } = useAgentOverview({ enabled: open && isAdmin })

  // 管理员身份丢失（切账号等）时把对话对象拉回常规助手
  useEffect(() => {
    if (!isAdmin && chatAgentType !== 'assistant') setChatAgent('assistant')
  }, [isAdmin, chatAgentType, setChatAgent])

  const [sidebarWidth, setSidebarWidth] = useState(() =>
    readStoredWidth(
      SIDEBAR_STORAGE_KEY,
      DEFAULT_SIDEBAR_WIDTH,
      MIN_SIDEBAR_WIDTH,
      MAX_SIDEBAR_WIDTH,
    ),
  )
  const [sidebarResizing, setSidebarResizing] = useState(false)
  const sidebarStartXRef = useRef(0)
  const sidebarStartWidthRef = useRef(sidebarWidth)

  const [drawerWidth, setDrawerWidth] = useState(() =>
    readStoredWidth(
      DRAWER_STORAGE_KEY,
      DEFAULT_DRAWER_WIDTH,
      MIN_DRAWER_WIDTH,
      MAX_DRAWER_WIDTH,
    ),
  )
  const [drawerResizing, setDrawerResizing] = useState(false)
  const drawerStartXRef = useRef(0)
  const drawerStartWidthRef = useRef(drawerWidth)

  const isNarrow = useIsNarrowScreen()
  const [mobileListOpen, setMobileListOpen] = useState(false)

  useEffect(() => {
    if (!open) setMobileListOpen(false)
  }, [open])

  useEffect(() => {
    if (!open) return
    refresh()
  }, [open, threadId, refresh])

  useEffect(() => {
    if (!sidebarResizing) return
    document.body.style.cursor = 'col-resize'
    const handleMouseMove = (e: MouseEvent) => {
      const next = clamp(
        sidebarStartWidthRef.current + (e.clientX - sidebarStartXRef.current),
        MIN_SIDEBAR_WIDTH,
        MAX_SIDEBAR_WIDTH,
      )
      setSidebarWidth(next)
    }
    const handleMouseUp = () => {
      setSidebarResizing(false)
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(sidebarWidth))
    }
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
    }
  }, [sidebarResizing, sidebarWidth])

  useEffect(() => {
    if (!drawerResizing) return
    document.body.style.cursor = 'col-resize'
    const handleMouseMove = (e: MouseEvent) => {
      // 抽屉在右侧，左边缘向左拖动（clientX 减小）时宽度增加
      const next = clamp(
        drawerStartWidthRef.current + (drawerStartXRef.current - e.clientX),
        MIN_DRAWER_WIDTH,
        MAX_DRAWER_WIDTH,
      )
      setDrawerWidth(next)
    }
    const handleMouseUp = () => {
      setDrawerResizing(false)
      window.localStorage.setItem(DRAWER_STORAGE_KEY, String(drawerWidth))
    }
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
    }
  }, [drawerResizing, drawerWidth])

  const activeTitle = useMemo(() => {
    if (!threadId) return null
    return sessions.find((s) => s.thread_id === threadId)?.title ?? null
  }, [sessions, threadId])

  const handleDelete = async (value: string) => {
    await deleteSessionById(value)
    if (value === threadId) switchThread(undefined)
  }

  const handleSidebarResizeStart = (e: React.MouseEvent) => {
    e.preventDefault()
    setSidebarResizing(true)
    sidebarStartXRef.current = e.clientX
    sidebarStartWidthRef.current = sidebarWidth
  }

  const handleDrawerResizeStart = (e: React.MouseEvent) => {
    e.preventDefault()
    setDrawerResizing(true)
    drawerStartXRef.current = e.clientX
    drawerStartWidthRef.current = drawerWidth
  }

  const isResizing = sidebarResizing || drawerResizing

  const sidebarNode = (closeOnSelect: boolean) => (
    <AssistantSidebar
      sessions={sessions}
      activeThreadId={threadId}
      isLoading={isLoading}
      width={isNarrow ? 300 : sidebarWidth}
      onNewThread={() => {
        switchThread(undefined)
        if (closeOnSelect) setMobileListOpen(false)
      }}
      onSwitchThread={(id) => {
        switchThread(id)
        if (closeOnSelect) setMobileListOpen(false)
      }}
      onDeleteThread={handleDelete}
    />
  )

  return (
    <Drawer
      title={null}
      placement="right"
      open={open}
      onClose={closePanel}
      // 关闭按钮统一为头部右侧一个（AssistantHeader），去掉 Drawer 自带的角标 X
      closable={false}
      width={isNarrow ? '100%' : drawerWidth}
      styles={{ body: { padding: 0 } }}
    >
      <div className={`relative flex h-full bg-[#0c0e12] ${isResizing ? 'select-none' : ''}`}>
        {!isNarrow && (
          <div
            role="separator"
            aria-label="调整对话框宽度"
            onMouseDown={handleDrawerResizeStart}
            className="absolute left-0 top-0 bottom-0 z-10 w-1.5 cursor-col-resize bg-transparent hover:bg-blue-500/20 active:bg-blue-500/40"
          />
        )}
        {isNarrow ? (
          mobileListOpen && (
            <div className="absolute inset-0 z-20 flex">
              <div
                className="absolute inset-0 bg-black/60"
                onClick={() => setMobileListOpen(false)}
              />
              <div className="relative h-full">{sidebarNode(true)}</div>
            </div>
          )
        ) : (
          sidebarNode(false)
        )}
        {!isNarrow && (
          <div
            role="separator"
            aria-label="调整侧边栏宽度"
            onMouseDown={handleSidebarResizeStart}
            className="group relative z-10 w-1.5 shrink-0 cursor-col-resize bg-transparent hover:bg-blue-500/20 active:bg-blue-500/40"
          >
            <div className="absolute left-1/2 top-1/2 h-8 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gray-700 transition-colors group-hover:bg-blue-400 group-active:bg-blue-300" />
          </div>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <AssistantHeader
            title={activeTitle}
            onClose={closePanel}
            agentType={chatAgentType}
            agentItems={overview?.items ?? []}
            onSwitchAgent={isAdmin ? setChatAgent : undefined}
            showSessionsToggle={isNarrow}
            sessionsOpen={mobileListOpen}
            onToggleSessions={() => setMobileListOpen((v) => !v)}
          />
          {todos && todos.length > 0 && <TodoListBar todos={todos} />}
          <div className="min-h-0 flex-1">
            {/* key=chatAgentType：切换对话对象必须重挂载 runtime 换绑 agent 端点
                （线程态已由 setChatAgent 重置）。线程内切换不可加 key=threadId：
                threads.create 后 onThreadIdChange 会触发重挂载，销毁乐观消息 */}
            <AssistantErrorBoundary key={chatAgentType}>
              <AssistantRuntimeProvider agentType={chatAgentType}>
                <AssistantThread />
              </AssistantRuntimeProvider>
            </AssistantErrorBoundary>
          </div>
        </div>
      </div>
    </Drawer>
  )
}

export function AssistantFab() {
  const openPanel = useAssistantStore((state) => state.openPanel)
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem(FAB_COLLAPSED_KEY) === '1',
  )
  const pressTimerRef = useRef<number | null>(null)
  const suppressClickRef = useRef(false)
  const downPosRef = useRef<{ x: number; y: number } | null>(null)

  const collapse = () => {
    setCollapsed(true)
    localStorage.setItem(FAB_COLLAPSED_KEY, '1')
  }
  const expand = () => {
    setCollapsed(false)
    localStorage.setItem(FAB_COLLAPSED_KEY, '0')
  }

  const clearPressTimer = () => {
    if (pressTimerRef.current != null) {
      clearTimeout(pressTimerRef.current)
      pressTimerRef.current = null
    }
  }

  // 长按 500ms 收起；移动距离超阈值视为滚动/拖拽意图，取消计时
  const handlePointerDown = (e: React.PointerEvent) => {
    downPosRef.current = { x: e.clientX, y: e.clientY }
    clearPressTimer()
    pressTimerRef.current = window.setTimeout(() => {
      suppressClickRef.current = true
      navigator.vibrate?.(10)
      collapse()
    }, 500)
  }
  const handlePointerMove = (e: React.PointerEvent) => {
    const start = downPosRef.current
    if (!start) return
    if (Math.hypot(e.clientX - start.x, e.clientY - start.y) > 8) {
      clearPressTimer()
      downPosRef.current = null
    }
  }
  const handlePointerUp = () => {
    clearPressTimer()
    downPosRef.current = null
  }
  const handleClick = () => {
    if (suppressClickRef.current) {
      suppressClickRef.current = false
      return
    }
    openPanel()
  }
  // 桌面右键收起；同时兜住移动端长按触发的系统 contextmenu
  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    clearPressTimer()
    collapse()
  }

  useEffect(() => clearPressTimer, [])

  if (collapsed) {
    return (
      <Tooltip title="展开 AI 助手">
        <button
          type="button"
          onClick={expand}
          aria-label="展开 AI 助手"
          className="assistant-fab-collapsed fixed bottom-[88px] right-3 z-50 md:bottom-[52px]"
        >
          <img src={ASSISTANT_AVATAR} alt="" draggable={false} />
        </button>
      </Tooltip>
    )
  }

  return (
    <Tooltip title="AI 助手（长按收起）">
      <button
        type="button"
        onClick={handleClick}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onContextMenu={handleContextMenu}
        aria-label="打开 AI 助手"
        className="assistant-fab fixed bottom-20 right-4 z-50 md:bottom-6"
      >
        <img src={ASSISTANT_AVATAR} alt="" draggable={false} />
      </button>
    </Tooltip>
  )
}
