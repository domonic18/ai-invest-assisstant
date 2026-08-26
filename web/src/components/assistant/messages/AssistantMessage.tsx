import {
  CheckOutlined,
  CopyOutlined,
  DislikeOutlined,
  LikeOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { ActionBarPrimitive, MessagePrimitive } from '@assistant-ui/react'
import type { ToolCallMessagePartProps } from '@assistant-ui/react'

import { MarkdownContent } from './MarkdownContent'
import { MessageAvatar } from './MessageAvatar'
import { ReasoningBlock } from './ReasoningBlock'
import { ToolCallBlock } from './ToolCallBlock'

function Text({ text }: { text: string }) {
  return <MarkdownContent content={text} />
}

function Reasoning({ text }: { text: string }) {
  return <ReasoningBlock text={text} />
}

function ToolCall({ toolName, args, result }: ToolCallMessagePartProps) {
  return <ToolCallBlock toolName={toolName} args={args} result={result} />
}

function MessageActions() {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="mt-1 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100"
    >
      <ActionBarPrimitive.Copy
        copiedDuration={2000}
        title="复制"
        className="rounded p-1 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300 [&[data-copied]_span.copy-icon]:hidden [&:not([data-copied])_span.check-icon]:hidden"
      >
        <span className="copy-icon">
          <CopyOutlined />
        </span>
        <span className="check-icon">
          <CheckOutlined />
        </span>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Reload
        title="重新生成"
        className="rounded p-1 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300"
      >
        <ReloadOutlined />
      </ActionBarPrimitive.Reload>
      <ActionBarPrimitive.FeedbackPositive
        title="有用"
        className="rounded p-1 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300"
      >
        <LikeOutlined />
      </ActionBarPrimitive.FeedbackPositive>
      <ActionBarPrimitive.FeedbackNegative
        title="无用"
        className="rounded p-1 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300"
      >
        <DislikeOutlined />
      </ActionBarPrimitive.FeedbackNegative>
    </ActionBarPrimitive.Root>
  )
}

export function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="group mb-5 flex gap-3">
      <MessageAvatar role="assistant" />
      <div className="min-w-0 flex-1 space-y-1">
        <div
          className="rounded-2xl rounded-tl-sm border border-gray-700/50 bg-[#1f232c] px-4 py-3 shadow-sm"
        >
          <MessagePrimitive.Content
            components={{
              Text,
              Reasoning,
              tools: { Fallback: ToolCall },
            }}
          />
        </div>
        <MessageActions />
      </div>
    </MessagePrimitive.Root>
  )
}
