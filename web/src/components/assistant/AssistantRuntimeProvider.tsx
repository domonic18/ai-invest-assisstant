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

import { useAssistantStore } from '@/stores/assistant'

import { createAssistantRuntimeAdapter } from './runtimeAdapter'

export function AssistantRuntimeProvider({ children }: { children: ReactNode }) {
  const threadId = useAssistantStore((state) => state.threadId)
  const onThreadIdChange = useAssistantStore((state) => state.switchThread)
  const adapter = useMemo(() => createAssistantRuntimeAdapter(), [])

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
