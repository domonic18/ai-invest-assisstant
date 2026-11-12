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

import { createAssistantClient, createThread } from '@/api/assistant'
import type { AssistantAgentType } from '@/api/assistant'
import { buildPageContext } from '@/utils/pageContext'

import { useAssistantStore } from '@/stores/assistant'

import { dispatchCustomEvent, dispatchUpdates } from './assistantEventDispatcher'
import type { StateWithTasks } from './runtimeUtils'

const ASSISTANT_ID = 'invest-assistant'

/**
 * SDK 空闲看门狗固定窗口（ms）：后端每 15s 一帧心跳注释，60s 无任何字节
 * 即 4 帧连续丢失，必然是半开/黑洞连接——立即中断流并触发对账恢复。
 * 固定模式从首字节起生效，不依赖看门狗先观察到心跳（auto 模式的限制）
 */
const STREAM_IDLE_TIMEOUT_MS = 60_000
/** 断连恢复轮询间隔 */
const RECOVERY_POLL_INTERVAL_MS = 3_000
/** 恢复轮询最长等待：超过后认为任务仍在后台长跑，提示用户稍后回看 */
const RECOVERY_MAX_WAIT_MS = 5 * 60_000

function abortableSleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal?.aborted) return resolve()
    const finish = () => {
      clearTimeout(timer)
      signal?.removeEventListener('abort', finish)
      resolve()
    }
    const timer = setTimeout(finish, ms)
    signal?.addEventListener('abort', finish)
  })
}

function noticeMessage(content: string) {
  return {
    event: 'messages',
    data: [
      {
        type: 'ai',
        id: `stream-notice-${Date.now()}`,
        content,
      },
      {},
    ],
  }
}

interface RecoverableThreadState extends StateWithTasks {
  values?: { messages?: unknown[] } | null
  /** 后端 run_registry 注入：线程是否有正在执行的 run */
  active?: boolean
}

/**
 * 流中断后与服务端真相源对账（checkpoint 为准，不信任乐观态）：
 * - run 仍活跃：轮询等待（UI 保持真实运行态）；
 * - run 已结束：一条 node 包裹的 updates 帧把服务端终态消息按 id upsert
 *   回 runtime（补齐 ToolMessage 结算工具调用、替换断点处的半截 AI 消息），
 *   同时经 updates 分派器幂等重派断连期间丢失的页面事件/问题卡标记；
 * - 超时仍活跃 / 状态不可达：合成提示消息说明去向，用户稍后回看。
 */
async function* recoverAfterStreamFailure(
  client: Client,
  externalId: string,
  signal?: AbortSignal,
) {
  const deadline = Date.now() + RECOVERY_MAX_WAIT_MS
  let state: RecoverableThreadState | null = null
  while (true) {
    if (signal?.aborted) return
    try {
      state = (await client.threads.getState(externalId)) as unknown as RecoverableThreadState
    } catch {
      yield noticeMessage(
        '连接已中断，且暂时无法确认任务状态。请检查网络；稍后重新打开本会话即可查看已完成的结果。',
      )
      return
    }
    if (state.active !== true) break
    if (Date.now() >= deadline) {
      yield noticeMessage(
        '连接已中断，任务仍在后台执行。已完成的工作不会丢失，稍后重新打开本会话即可查看结果。',
      )
      return
    }
    await abortableSleep(RECOVERY_POLL_INTERVAL_MS, signal)
  }
  const messages = (state?.values?.messages ?? []) as unknown[]
  if (messages.length > 0) {
    yield { event: 'updates', data: { recovered: { messages } } } as never
  }
}

export interface AssistantAdapterOptions {
  /** trading：新线程经自有端点创建并携带 agent_type（SDK threads.create 白名单序列化带不上扩展字段），由后端分流至交易 Agent 运行时 */
  agentType?: AssistantAgentType
}

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
  options: AssistantAdapterOptions = {},
): AssistantRuntimeAdapter {
  // 后端会话即 remote 线程。默认的 InMemory adapter 不认识列表外的线程 id，
  // 切换历史会话时 fetch 会拒绝且被 runtime 静默吞掉（界面无反应），
  // 因此覆写 initialize（新会话真实 create）与 fetch（历史会话直接采用传入 id）。
  // SDK client 的 defaultHeaders 在构造时固化，必须每次调用时重建以读取最新 token。
  const threadListAdapter = new InMemoryThreadListAdapter()
  threadListAdapter.initialize = async () => {
    if (options.agentType && options.agentType !== 'assistant') {
      const thread = await createThread({ agent_type: options.agentType })
      return { remoteId: thread.thread_id, externalId: thread.thread_id }
    }
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
      let client: Client | null = null
      let externalId = ''
      let receivedChunk = false
      try {
        const initialized = await config.initialize()
        if (!initialized.externalId) throw new Error('线程尚未初始化')
        externalId = initialized.externalId
        client = createClient()
        const stream = await client.runs.stream(externalId, ASSISTANT_ID, {
          input: messages.length ? { messages } : null,
          command: config.command as never,
          // 发送瞬间读取 window.location 与 store 快照（零订阅，实时反映当前
          // 页面、?code= 与知识库开关；use_kb 缺省由后端按开启处理）
          metadata: {
            page_context: buildPageContext(window.location),
            use_kb: useAssistantStore.getState().useKb,
          },
          checkpoint: config.checkpointId
            ? {
                checkpoint_id: config.checkpointId,
                checkpoint_ns: '',
                checkpoint_map: {},
              }
            : undefined,
          streamMode: ['messages', 'updates', 'custom'],
          signal: config.abortSignal,
          // 固定窗口空闲看门狗：半开连接在窗口内被检出并抛 StreamIdleTimeoutError，
          // 由 catch 的对账恢复接管（auto 模式须先观察到 ≥2 帧心跳才武装）
          streamIdleReconnect: STREAM_IDLE_TIMEOUT_MS,
        })
        for await (const chunk of stream) {
          receivedChunk = true
          // 配额耗尽错误帧追加引导文案（arch/07 §7.2：AI 拦截须指引配 Key/联系管理员）
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
      } catch (error) {
        // 用户主动停止走 abort 路径，由 SDK 上游静默处理，不视为失败
        if (config.abortSignal?.aborted) throw error
        // receivedChunk 为真时 client/externalId 必已赋值（首帧必经 initialize 与 runs.stream）
        if (!receivedChunk || !client || !externalId) {
          // 流前错误（422/网络断/auth 失败）会被 langgraph-sdk 静默吞掉，
          // 界面零反馈形似假死（2026-11-10「发继续没反应」事故）；合成一条
          // AI 提示消息让用户直接在对话框看到失败原因
          const detail = error instanceof Error ? error.message : String(error)
          yield noticeMessage(
            `AI 请求发送失败：${detail}。请检查网络后重试；若持续失败请联系管理员。`,
          )
          return
        }
        // 流中断（半开超时/网络错误）：服务端可能仍在执行也可能已完成，
        // 以 checkpoint 真相源对账恢复终态，不把乐观态当事实
        // （2026-11-11「执行中永挂」事故的根治路径）
        yield* recoverAfterStreamFailure(client, externalId, config.abortSignal)
      }
    },
    eventHandlers: {
      onUpdates: dispatchUpdates,
      onCustomEvent: dispatchCustomEvent,
    },
  }
}
