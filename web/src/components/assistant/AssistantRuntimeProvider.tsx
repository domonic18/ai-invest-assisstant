/**
 * 助手运行时装配（瘦 Provider）：线程态始终走全局 store（侧边栏面板是唯一
 * 宿主），agentType 决定后端对话对象（'assistant' 或交易 Agent agent_key），
 * 切换对话对象时由调用方以 key 重挂载换绑端点。
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
  /** 'assistant'（默认）= 常规助手；交易 Agent 传其 agent_key */
  agentType?: AssistantAgentType
}

export function AssistantRuntimeProvider({
  children,
  agentType = 'assistant',
}: AssistantRuntimeProviderProps) {
  const threadId = useAssistantStore((state) => state.threadId)
  const onThreadIdChange = useAssistantStore((state) => state.switchThread)
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
