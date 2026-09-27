/**
 * 助手运行时装配（瘦 Provider）：只订阅 threadId（运行时必需），
 * 全部 SDK 集成点经 runtimeAdapter（useMemo 稳定引用）注入。
 * 禁止在此组件订阅业务 store 或内联配置对象——Provider 重渲染 =
 * 侧边栏全树重渲染，曾因此触发 assistant-ui 运行时渲染期崩溃。
 */

import type { ReactNode } from 'react'
import { AssistantRuntimeProvider as AuiRuntimeProvider } from '@assistant-ui/react'
import { useLangGraphRuntime } from '@assistant-ui/react-langgraph'
import { useMemo } from 'react'

import { createAssistantClient } from '@/api/assistant'
import type { AssistantAgentType } from '@/api/assistant'
import { useAssistantStore } from '@/stores/assistant'

import { createAssistantRuntimeAdapter } from './runtimeAdapter'

interface AssistantRuntimeProviderProps {
  children: ReactNode
  /** assistant（默认）：全局抽屉，线程态走全局 store；agent_key：页内嵌会话，线程态由挂载方持有 */
  agentType?: AssistantAgentType
  /** 交易 Agent 模式的受控线程 id（assistant 模式忽略） */
  threadId?: string
  /** 交易 Agent 模式的线程回调（assistant 模式忽略） */
  onThreadIdChange?: (threadId: string | undefined) => void
}

export function AssistantRuntimeProvider({
  children,
  agentType = 'assistant',
  threadId: externalThreadId,
  onThreadIdChange: externalOnThreadIdChange,
}: AssistantRuntimeProviderProps) {
  const storeThreadId = useAssistantStore((state) => state.threadId)
  const storeSwitchThread = useAssistantStore((state) => state.switchThread)
  const isTrading = agentType !== 'assistant'
  const threadId = isTrading ? externalThreadId : storeThreadId
  const onThreadIdChange = isTrading ? externalOnThreadIdChange : storeSwitchThread
  const adapter = useMemo(
    () => createAssistantRuntimeAdapter(createAssistantClient, { agentType }),
    [agentType],
  )

  const runtime = useLangGraphRuntime({
    threadId,
    onThreadIdChange,
    unstable_allowCancellation: true,
    unstable_threadListAdapter: adapter.threadListAdapter,
    eventHandlers: adapter.eventHandlers,
    load: adapter.load,
    stream: adapter.stream,
  })

  return <AuiRuntimeProvider runtime={runtime}>{children}</AuiRuntimeProvider>
}
