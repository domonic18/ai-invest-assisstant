import {
  ThreadPrimitive,
  useAuiState,
} from '@assistant-ui/react'
import { useCallback, useRef } from 'react'

import { AssistantEmptyState } from './AssistantEmptyState'
import {
  SuggestedQuestionContext,
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

export function AssistantThread() {
  const isLoading = useAuiState((s) => s.thread.isLoading)
  const sendRef = useRef<(question: string) => void>(() => {})
  const registerSend = useCallback((fn: (question: string) => void) => {
    sendRef.current = fn
  }, [])
  const sendQuestion = useCallback((question: string) => {
    sendRef.current(question)
  }, [])

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
        <Composer registerSend={registerSend} />
      </ThreadPrimitive.Root>
    </SuggestedQuestionContext.Provider>
  )
}
