import type { ReactNode } from 'react'
import {
  AssistantRuntimeProvider as AuiRuntimeProvider,
  InMemoryThreadListAdapter,
} from '@assistant-ui/react'
import { useLangGraphRuntime } from '@assistant-ui/react-langgraph'
import { useLocation } from 'react-router-dom'

import { createAssistantClient } from '@/api/assistant'
import { useAssistantStore, type PageAssistantResult, type TodoStep } from '@/stores/assistant'
import { buildPageContext } from '@/utils/pageContext'

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

type StateWithTasks = {
  tasks?: Array<{ interrupts?: Array<Record<string, unknown>> }>
}

/** 从根图 updates 载荷（{node: state_update}）中提取 deepagents todos */
function extractTodos(updates: unknown): TodoStep[] | undefined {
  if (typeof updates !== 'object' || updates === null) return undefined
  for (const node of Object.values(updates as Record<string, unknown>)) {
    if (typeof node !== 'object' || node === null) continue
    const todos = (node as Record<string, unknown>).todos
    if (Array.isArray(todos)) return todos as TodoStep[]
  }
  return undefined
}

/** 从 messages 列表或 updates 中提取产业链分析完成事件。 */
function extractPageResultFromMessages(messages: unknown[]): PageAssistantResult | null {
  for (const msg of messages) {
    if (typeof msg !== 'object' || msg === null) continue
    const typed = msg as Record<string, unknown>
    if (typed.type !== 'tool') continue
    const content = typed.content
    if (typeof content !== 'object' || content === null) continue
    const event = (content as Record<string, unknown>).__event__
    if (typeof event !== 'object' || event === null) continue
    const e = event as Record<string, unknown>
    if (e.type !== 'industry_chain.analysis_complete') continue
    return {
      type: 'industry_chain.analysis_complete',
      industry: String(e.industry ?? ''),
      versionId: Number(e.version_id),
      versionNo: Number(e.version_no),
      createdAt: e.created_at ? String(e.created_at) : undefined,
    }
  }
  return null
}

function extractPageResult(updates: unknown): PageAssistantResult | null {
  if (typeof updates !== 'object' || updates === null) return null
  for (const node of Object.values(updates as Record<string, unknown>)) {
    if (typeof node !== 'object' || node === null) continue
    const messages = (node as Record<string, unknown>).messages
    if (Array.isArray(messages)) {
      const result = extractPageResultFromMessages(messages)
      if (result) return result
    }
  }
  return null
}

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
        const e = event as unknown as Record<string, unknown>
        if (e.type === 'industry_chain.analysis_complete') {
          useAssistantStore.getState().setPageResult({
            type: 'industry_chain.analysis_complete',
            industry: String(e.industry ?? ''),
            versionId: Number(e.version_id),
            versionNo: Number(e.version_no),
            createdAt: e.created_at ? String(e.created_at) : undefined,
          })
        }
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
