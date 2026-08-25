import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Drawer, Popconfirm, Select, Space } from 'antd'
import { useEffect } from 'react'

import { deleteSession, fetchSessions } from '@/api/assistant'
import { useAssistantStore, type TodoStep } from '@/stores/assistant'

import { AssistantThread } from './AssistantThread'
import { AssistantRuntimeProvider } from './AssistantRuntimeProvider'

const TODO_MARKERS: Record<TodoStep['status'], string> = {
  completed: '✓',
  in_progress: '◐',
  pending: '○',
}

function TodoListBar({ todos }: { todos: TodoStep[] }) {
  return (
    <div className="border-b border-gray-800 px-3 py-2">
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

  const queryClient = useQueryClient()
  const { data } = useQuery({
    queryKey: ['assistant-sessions'],
    queryFn: () => fetchSessions({ limit: 50 }),
    enabled: open,
  })

  // 面板打开或活跃线程变化（新会话创建/切换）时刷新会话列表，
  // 否则 TanStack Query 会一直用首次打开时的旧数据（当时可能为空）
  useEffect(() => {
    if (open) {
      queryClient.invalidateQueries({ queryKey: ['assistant-sessions'] })
    }
  }, [open, threadId, queryClient])

  const options = (data?.sessions ?? []).map((session) => ({
    value: session.thread_id,
    label: session.title || '新会话',
  }))

  const handleDelete = async (value: string) => {
    await deleteSession(value)
    await queryClient.invalidateQueries({ queryKey: ['assistant-sessions'] })
    if (value === threadId) switchThread(undefined)
  }

  return (
    <Drawer
      title="AI 投研助手"
      placement="right"
      open={open}
      onClose={closePanel}
      width={480}
      styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}
    >
      <div className="flex items-center gap-2 border-b border-gray-800 px-3 py-2">
        <Select
          className="flex-1"
          placeholder="新会话"
          value={threadId}
          options={options}
          onChange={(value) => switchThread(value)}
          allowClear
          onClear={() => switchThread(undefined)}
          popupMatchSelectWidth={false}
        />
        <Button size="small" onClick={() => switchThread(undefined)}>
          新会话
        </Button>
        {threadId && (
          <Popconfirm
            title="删除该会话？"
            onConfirm={() => handleDelete(threadId)}
            okText="删除"
            cancelText="取消"
          >
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        )}
      </div>
      {todos && todos.length > 0 && <TodoListBar todos={todos} />}
      <div className="min-h-0 flex-1">
        {/* 不能加 key：runtime 原生支持 threadId 受控切换，加 key 会在
            threads.create 后因 onThreadIdChange 触发整个 runtime 重挂载，
            销毁乐观消息并中断进行中的流 */}
        <AssistantRuntimeProvider>
          <AssistantThread />
        </AssistantRuntimeProvider>
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
