import {
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAuiState,
} from '@assistant-ui/react'
import type {
  ReasoningMessagePartProps,
  ToolCallMessagePartProps,
} from '@assistant-ui/react'
import { MarkdownTextPrimitive } from '@assistant-ui/react-markdown'

const Text = () => <MarkdownTextPrimitive />

function Reasoning({ text }: ReasoningMessagePartProps) {
  if (!text) return null
  return (
    <details className="mb-2 rounded-md border border-gray-700/60 bg-gray-800/40 text-xs text-gray-400">
      <summary className="cursor-pointer select-none px-2 py-1 hover:text-gray-200">
        思考过程
      </summary>
      <div className="max-h-48 overflow-auto whitespace-pre-wrap px-3 pb-2">
        {text}
      </div>
    </details>
  )
}

function ToolCall({ toolName, args, result }: ToolCallMessagePartProps) {
  return (
    <details className="mb-2 rounded-md border border-sky-900/60 bg-sky-950/30 text-xs">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-2 py-1 text-sky-300">
        <span className="font-mono">{toolName}</span>
        {result == null ? (
          <span className="animate-pulse">运行中…</span>
        ) : (
          <span className="text-gray-500">已完成</span>
        )}
      </summary>
      <div className="space-y-1 px-3 pb-2 text-gray-300">
        <div>
          <span className="text-gray-500">参数：</span>
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">
            {JSON.stringify(args, null, 2)}
          </pre>
        </div>
        {result != null && (
          <div>
            <span className="text-gray-500">结果：</span>
            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap">
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </details>
  )
}

const UserMessage = () => (
  <MessagePrimitive.Root className="mb-4 flex justify-end">
    <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-blue-600 px-3 py-2 text-sm text-white">
      <MessagePrimitive.Content />
    </div>
  </MessagePrimitive.Root>
)

const AssistantMessage = () => (
  <MessagePrimitive.Root className="mb-4">
    <div className="max-w-full text-sm leading-relaxed text-gray-100 [&_table]:my-2 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-gray-700 [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-gray-700 [&_th]:bg-gray-800 [&_th]:px-2 [&_th]:py-1">
      <MessagePrimitive.Content
        components={{
          Text,
          Reasoning,
          tools: { Fallback: ToolCall },
        }}
      />
    </div>
  </MessagePrimitive.Root>
)

const Composer = () => (
  <ComposerPrimitive.Root className="flex items-end gap-2 border-t border-gray-800 p-3">
    <ComposerPrimitive.Input
      rows={1}
      autoFocus
      placeholder="问我任何投研问题，如「平安银行最近走势如何」"
      className="max-h-32 flex-1 resize-none rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 placeholder:text-gray-500 focus:border-blue-500 focus:outline-none"
    />
    <ThreadPrimitive.If running>
      <ComposerPrimitive.Cancel className="rounded-lg border border-red-700 bg-red-900/40 px-3 py-2 text-sm text-red-300 hover:bg-red-900/70">
        停止
      </ComposerPrimitive.Cancel>
    </ThreadPrimitive.If>
    <ThreadPrimitive.If running={false}>
      <ComposerPrimitive.Send className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-40">
        发送
      </ComposerPrimitive.Send>
    </ThreadPrimitive.If>
  </ComposerPrimitive.Root>
)

/** 历史会话加载骨架屏：按真实消息布局（右用户气泡 + 左助手多行）占位，脉冲动画 */
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
      ))}
    </div>
  )
}

export function AssistantThread() {
  const isLoading = useAuiState((s) => s.thread.isLoading)

  return (
    <ThreadPrimitive.Root className="flex h-full flex-col">
      <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto px-4 py-4">
        {isLoading ? (
          <HistorySkeleton />
        ) : (
          <>
            <ThreadPrimitive.Empty>
              <div className="mt-16 text-center text-sm text-gray-500">
                AI 投研助手 · 支持行情、财务、资金流、竞价、新闻、研报问答
              </div>
            </ThreadPrimitive.Empty>
            <ThreadPrimitive.Messages
              components={{ UserMessage, AssistantMessage }}
            />
          </>
        )}
      </ThreadPrimitive.Viewport>
      <Composer />
    </ThreadPrimitive.Root>
  )
}
