/**
 * 助手运行时防腐层（Anti-Corruption Layer）：集中 @assistant-ui/langgraph-sdk
 * 的全部集成点（threadListAdapter / load / stream / eventHandlers），
 * Provider 只做装配、引用经 useMemo 稳定。SDK 回调签名与事件分派契约
 * 由 runtimeAdapter.test.ts 钉死，SDK 升级只改本文件。
 *
 * 纪律：本模块不订阅任何 React 状态——页面上下文在发送瞬间读
 * window.location（纯函数 buildPageContext），避免 Provider 随页面
 * 状态变化重渲染（曾致 assistant-ui 运行时渲染期空引用整页崩溃）。
 */

import { InMemoryThreadListAdapter } from '@assistant-ui/react'
import type {
  LangChainMessage,
  LangGraphStreamCallback,
  OnCustomEventCallback,
  OnUpdatesEventCallback,
} from '@assistant-ui/react-langgraph'
import type { Client } from '@langchain/langgraph-sdk'

import { createAssistantClient } from '@/api/assistant'
import { buildPageContext } from '@/utils/pageContext'

import { dispatchCustomEvent, dispatchUpdates } from './assistantEventDispatcher'
import type { StateWithTasks } from './runtimeUtils'

const ASSISTANT_ID = 'invest-assistant'

export interface AssistantRuntimeAdapter {
  threadListAdapter: InMemoryThreadListAdapter
  load: (
    threadId: string,
    config?: { signal: AbortSignal },
  ) => Promise<{
    messages: LangChainMessage[]
    interrupts?: never
    uiMessages?: never
  }>
  stream: LangGraphStreamCallback<LangChainMessage>
  eventHandlers: {
    onUpdates: OnUpdatesEventCallback
    /** SDK 契约（types.d.ts 钉死）：回调签名 (type, data)，data 为 custom 事件载荷 */
    onCustomEvent: OnCustomEventCallback
  }
}

export function createAssistantRuntimeAdapter(
  createClient: () => Client = createAssistantClient,
): AssistantRuntimeAdapter {
  // 后端会话即 remote 线程。默认的 InMemory adapter 不认识列表外的线程 id，
  // 切换历史会话时 fetch 会拒绝且被 runtime 静默吞掉（界面无反应），
  // 因此覆写 initialize（新会话真实 create）与 fetch（历史会话直接采用传入 id）。
  // SDK client 的 defaultHeaders 在构造时固化，必须每次调用时重建以读取最新 token。
  const threadListAdapter = new InMemoryThreadListAdapter()
  threadListAdapter.initialize = async () => {
    const client = createClient()
    const thread = await client.threads.create()
    return { remoteId: thread.thread_id, externalId: thread.thread_id }
  }
  threadListAdapter.fetch = async (threadId: string) => ({
    status: 'regular' as const,
    remoteId: threadId,
    externalId: threadId,
  })

  return {
    threadListAdapter,
    load: async (externalId: string) => {
      const client = createClient()
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
      const client = createClient()
      const stream = await client.runs.stream(externalId, ASSISTANT_ID, {
        input: messages.length ? { messages } : null,
        command: config.command as never,
        // 发送瞬间读取 window.location（零订阅，实时反映当前页面与 ?code=）
        metadata: { page_context: buildPageContext(window.location) },
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
        // 配额耗尽错误帧追加引导文案（arch/10 §7.2：AI 拦截须指引配 Key/联系管理员）
        if (chunk.event === 'error') {
          const data = chunk.data as
            | { error_code?: string; error?: string }
            | undefined
          if (data?.error_code === 'quota_exhausted') {
            yield {
              event: chunk.event,
              data: {
                ...data,
                error: `${data.error ?? 'AI 配额已用尽'}（可前往「设置 → 我的模型」配置自有 API Key，或联系管理员追加配额）`,
              },
            }
            continue
          }
        }
        yield { event: chunk.event, data: chunk.data }
      }
    },
    eventHandlers: {
      onUpdates: dispatchUpdates,
      onCustomEvent: dispatchCustomEvent,
    },
  }
}
