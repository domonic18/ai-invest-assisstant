import {
  ThreadPrimitive,
  useAui,
  useAuiState,
} from '@assistant-ui/react'
import { useCallback, useEffect } from 'react'

import { useAssistantStore } from '@/stores/assistant'

import { AssistantEmptyState } from './AssistantEmptyState'
import {
  SuggestedQuestionContext,
  useSuggestedQuestion,
} from './SuggestedQuestionContext'
import { Composer } from './composer/Composer'
import { AssistantMessage } from './messages/AssistantMessage'
import { UserMessage } from './messages/UserMessage'

/** 历史会话加载骨架屏 */
function HistorySkeleton() {
  const widths = [
    ['w-36', 'w-64', 'w-48'],
    ['w-44', 'w-72', 'w-40'],
  ]
  return (
    <div aria-busy="true" aria-label="正在加载会话记录">
      {widths.map((lines, round) => (
        <div key={round} className="mb-4">
          <div className="mb-4 flex justify-end">
            <div
              className="h-9 animate-pulse rounded-2xl rounded-br-sm bg-gray-700/50"
              style={{ width: round === 0 ? 160 : 120 }}
            />
          </div>
          <div className="flex gap-3">
            <div className="h-7 w-7 shrink-0 animate-pulse rounded-full bg-gray-700/50" />
            <div className="space-y-2">
              {lines.map((width, i) => (
                <div
                  key={i}
                  className={`h-4 animate-pulse rounded bg-gray-700/35 ${width}`}
                  style={{ animationDelay: `${round * 120 + i * 80}ms` }}
                />
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function PendingQuestionSender() {
  const sendQuestion = useSuggestedQuestion()
  const pendingQuestion = useAssistantStore((state) => state.pendingQuestion)
  const clearPendingQuestion = useAssistantStore((state) => state.clearPendingQuestion)
  // 历史会话加载中或上一轮运行中时无法追加消息；
  // 就绪前保留 pendingQuestion，就绪后再发送，避免预置问题被静默丢弃
  const isLoading = useAuiState((s) => s.thread.isLoading)
  const isRunning = useAuiState((s) => s.thread.isRunning)

  useEffect(() => {
    if (!pendingQuestion || isLoading || isRunning) return
    sendQuestion(pendingQuestion)
    clearPendingQuestion()
  }, [pendingQuestion, isLoading, isRunning, sendQuestion, clearPendingQuestion])

  return null
}

export function AssistantThread() {
  const isLoading = useAuiState((s) => s.thread.isLoading)
  const aui = useAui()
  // 直写 thread 而非 composer.setText + send：assistant-ui 的 setText 经
  // flushTapSync 延迟生效，同一 tick 内的 send() 读到旧的 canSend 会静默 no-op
  const sendQuestion = useCallback(
    (question: string) => {
      aui.thread.append(question)
    },
    [aui],
  )

  return (
    <SuggestedQuestionContext.Provider value={{ sendQuestion }}>
      <ThreadPrimitive.Root className="flex h-full flex-col bg-[#0c0e12]">
        <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto px-4 py-4">
          {isLoading ? (
            <HistorySkeleton />
          ) : (
            <>
              <ThreadPrimitive.Empty>
                <AssistantEmptyState />
              </ThreadPrimitive.Empty>
              <ThreadPrimitive.Messages
                components={{ UserMessage, AssistantMessage }}
              />
            </>
          )}
        </ThreadPrimitive.Viewport>
        <Composer />
        <PendingQuestionSender />
      </ThreadPrimitive.Root>
    </SuggestedQuestionContext.Provider>
  )
}
