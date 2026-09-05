import type { ReactNode } from 'react'
import {
  AssistantRuntimeProvider as AuiRuntimeProvider,
  InMemoryThreadListAdapter,
} from '@assistant-ui/react'
import { useLangGraphRuntime } from '@assistant-ui/react-langgraph'
import { useLocation } from 'react-router-dom'

import { createAssistantClient } from '@/api/assistant'
import { useAssistantStore } from '@/stores/assistant'
import { buildPageContext } from '@/utils/pageContext'
import { parsePageEvent } from './pageEvents'
import { extractPageResult, extractTodos, type StateWithTasks } from './runtimeUtils'

const ASSISTANT_ID = 'invest-assistant'

// 后端会话即 remote 线程。默认的 InMemory adapter 不认识列表外的线程 id，
// 切换历史会话时 fetch 会拒绝且被 runtime 静默吞掉（界面无反应），
// 因此覆写 initialize（新会话真实 create）与 fetch（历史会话直接采用传入 id）。
// SDK client 的 defaultHeaders 在构造时固化，必须每次调用时重建以读取最新 token。
const threadListAdapter = new InMemoryThreadListAdapter()
threadListAdapter.initialize = async () => {
  const client = createAssistantClient()
  const thread = await client.threads.create()
  return { remoteId: thread.thread_id, externalId: thread.thread_id }
}
threadListAdapter.fetch = async (threadId: string) => ({
  status: 'regular' as const,
  remoteId: threadId,
  externalId: threadId,
})

export function AssistantRuntimeProvider({ children }: { children: ReactNode }) {
  const threadId = useAssistantStore((state) => state.threadId)
  const onThreadIdChange = useAssistantStore((state) => state.switchThread)
  const location = useLocation()

  const runtime = useLangGraphRuntime({
    threadId,
    onThreadIdChange,
    unstable_allowCancellation: true,
    unstable_threadListAdapter: threadListAdapter,
    eventHandlers: {
      onUpdates: (updates) => {
        const todos = extractTodos(updates)
        if (todos) useAssistantStore.getState().setTodos(todos)
        const pageResult = extractPageResult(updates)
        if (pageResult) useAssistantStore.getState().setPageResult(pageResult)
      },
      onCustomEvent: (event) => {
        const parsed = parsePageEvent(event)
        if (parsed) useAssistantStore.getState().setPageResult(parsed.result)
      },
    },
    load: async (externalId: string) => {
      const client = createAssistantClient()
      const state = await client.threads.getState(externalId)
      const values = (state.values ?? {}) as { messages?: unknown[] }
      const tasks = (state as unknown as StateWithTasks).tasks
      const interrupts = tasks?.[0]?.interrupts
      return {
        messages: (values.messages ?? []) as never,
        interrupts: interrupts?.length ? (interrupts as never) : undefined,
      }
    },
    stream: async function* (messages, config) {
      const { externalId } = await config.initialize()
      if (!externalId) throw new Error('线程尚未初始化')
      const client = createAssistantClient()
      const stream = await client.runs.stream(externalId, ASSISTANT_ID, {
        input: messages.length ? { messages } : null,
        command: config.command,
        metadata: { page_context: buildPageContext(location.pathname) },
        checkpoint: config.checkpointId
          ? {
              checkpoint_id: config.checkpointId,
              checkpoint_ns: '',
              checkpoint_map: {},
            }
          : undefined,
        streamMode: ['messages', 'updates', 'custom'],
        signal: config.abortSignal,
      })
      for await (const chunk of stream) {
        yield { event: chunk.event, data: chunk.data }
      }
    },
  })

  return <AuiRuntimeProvider runtime={runtime}>{children}</AuiRuntimeProvider>
}
