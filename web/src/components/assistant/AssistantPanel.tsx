import { Button, Drawer, Space } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useAssistantSessions } from './hooks/useAssistantSessions'
import { useAssistantStore, type TodoStep } from '@/stores/assistant'

import { AssistantHeader } from './AssistantHeader'
import { AssistantSidebar } from './AssistantSidebar'
import { AssistantThread } from './AssistantThread'
import { AssistantRuntimeProvider } from './AssistantRuntimeProvider'

const TODO_MARKERS: Record<TodoStep['status'], string> = {
  completed: '✓',
  in_progress: '◐',
  pending: '○',
}

const MIN_SIDEBAR_WIDTH = 220
const MAX_SIDEBAR_WIDTH = 400
const DEFAULT_SIDEBAR_WIDTH = 260
const SIDEBAR_STORAGE_KEY = 'assistant-sidebar-width'

const MIN_DRAWER_WIDTH = 520
const MAX_DRAWER_WIDTH = 960
const DEFAULT_DRAWER_WIDTH = 760
const DRAWER_STORAGE_KEY = 'assistant-drawer-width'

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

function readStoredWidth(
  key: string,
  defaultValue: number,
  min: number,
  max: number,
): number {
  if (typeof window === 'undefined') return defaultValue
  const raw = window.localStorage.getItem(key)
  const value = raw ? Number.parseInt(raw, 10) : NaN
  return Number.isFinite(value) ? clamp(value, min, max) : defaultValue
}

function TodoListBar({ todos }: { todos: TodoStep[] }) {
  return (
    <div className="border-b border-gray-800 px-4 py-2">
      <div className="mb-1 text-xs text-gray-500">执行计划</div>
      <ol className="space-y-1">
        {todos.map((todo, index) => (
          <li
            key={index}
            className={`flex items-start gap-2 text-xs ${
              todo.status === 'in_progress'
                ? 'text-blue-300'
                : todo.status === 'completed'
                  ? 'text-gray-500'
                  : 'text-gray-400'
            }`}
          >
            <span
              className={`w-4 shrink-0 text-center ${
                todo.status === 'in_progress' ? 'animate-pulse' : ''
              }`}
            >
              {TODO_MARKERS[todo.status]}
            </span>
            <span className={todo.status === 'completed' ? 'line-through' : ''}>
              {todo.content}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

export function AssistantPanel() {
  const open = useAssistantStore((state) => state.open)
  const closePanel = useAssistantStore((state) => state.closePanel)
  const threadId = useAssistantStore((state) => state.threadId)
  const switchThread = useAssistantStore((state) => state.switchThread)
  const todos = useAssistantStore((state) => state.todos)

  const { sessions, isLoading, deleteSessionById, refresh } = useAssistantSessions({ enabled: open })

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

  return (
    <Drawer
      title={null}
      placement="right"
      open={open}
      onClose={closePanel}
      width={drawerWidth}
      styles={{ body: { padding: 0 } }}
    >
      <div className={`relative flex h-full bg-[#0c0e12] ${isResizing ? 'select-none' : ''}`}>
        <div
          role="separator"
          aria-label="调整对话框宽度"
          onMouseDown={handleDrawerResizeStart}
          className="absolute left-0 top-0 bottom-0 z-10 w-1.5 cursor-col-resize bg-transparent hover:bg-blue-500/20 active:bg-blue-500/40"
        />
        <AssistantSidebar
          sessions={sessions}
          activeThreadId={threadId}
          isLoading={isLoading}
          width={sidebarWidth}
          onNewThread={() => switchThread(undefined)}
          onSwitchThread={(id) => switchThread(id)}
          onDeleteThread={handleDelete}
        />
        <div
          role="separator"
          aria-label="调整侧边栏宽度"
          onMouseDown={handleSidebarResizeStart}
          className="group relative z-10 w-1.5 shrink-0 cursor-col-resize bg-transparent hover:bg-blue-500/20 active:bg-blue-500/40"
        >
          <div className="absolute left-1/2 top-1/2 h-8 w-0.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-gray-700 transition-colors group-hover:bg-blue-400 group-active:bg-blue-300" />
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
          <AssistantHeader title={activeTitle} onClose={closePanel} />
          {todos && todos.length > 0 && <TodoListBar todos={todos} />}
          <div className="min-h-0 flex-1">
            {/* 不能加 key：runtime 原生支持 threadId 受控切换，加 key 会在
                threads.create 后因 onThreadIdChange 触发整个 runtime 重挂载，
                销毁乐观消息并中断进行中的流 */}
            <AssistantRuntimeProvider>
              <AssistantThread />
            </AssistantRuntimeProvider>
          </div>
        </div>
      </div>
    </Drawer>
  )
}

export function AssistantFab() {
  const openPanel = useAssistantStore((state) => state.openPanel)
  return (
    <Space.Compact className="fixed bottom-20 right-4 z-50 md:bottom-6">
      <Button
        type="primary"
        shape="circle"
        size="large"
        onClick={openPanel}
        title="AI 投研助手"
      >
        AI
      </Button>
    </Space.Compact>
  )
}
