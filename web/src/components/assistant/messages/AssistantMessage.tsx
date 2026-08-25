import { CheckOutlined, CopyOutlined, DislikeOutlined, LikeOutlined, ReloadOutlined } from '@ant-design/icons'
import { MessagePrimitive } from '@assistant-ui/react'
import type { ToolCallMessagePartProps } from '@assistant-ui/react'
import { useRef, useState } from 'react'

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

interface MessageActionsProps {
  contentRef: React.RefObject<HTMLDivElement>
}

function MessageActions({ contentRef }: MessageActionsProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    const node = contentRef.current
    if (!node) return
    const text = node.textContent ?? ''
    if (!text.trim()) return
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  return (
    <div className="mt-1 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
      <button
        type="button"
        title="复制"
        onClick={handleCopy}
        className="rounded p-1 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300"
      >
        {copied ? <CheckOutlined /> : <CopyOutlined />}
      </button>
      <button
        type="button"
        title="重新生成"
        className="rounded p-1 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300"
      >
        <ReloadOutlined />
      </button>
      <button
        type="button"
        title="有用"
        className="rounded p-1 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300"
      >
        <LikeOutlined />
      </button>
      <button
        type="button"
        title="无用"
        className="rounded p-1 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300"
      >
        <DislikeOutlined />
      </button>
    </div>
  )
}

export function AssistantMessage() {
  const contentRef = useRef<HTMLDivElement>(null)

  return (
    <MessagePrimitive.Root className="group mb-5 flex gap-3">
      <MessageAvatar role="assistant" />
      <div className="min-w-0 flex-1 space-y-1">
        <div
          ref={contentRef}
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
        <MessageActions contentRef={contentRef} />
      </div>
    </MessagePrimitive.Root>
  )
}
