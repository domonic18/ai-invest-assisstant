import { BulbOutlined } from '@ant-design/icons'
import { useState } from 'react'

interface ReasoningBlockProps {
  text: string
}

export function ReasoningBlock({ text }: ReasoningBlockProps) {
  const [open, setOpen] = useState(false)
  if (!text) return null

  return (
    <div className="mb-2 overflow-hidden rounded-lg border border-gray-700/60 bg-gray-800/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-gray-400 transition-colors hover:text-gray-200"
      >
        <BulbOutlined />
        <span className="flex-1">{open ? '隐藏思考过程' : '查看思考过程'}</span>
      </button>
      {open && (
        <div className="max-h-48 overflow-auto whitespace-pre-wrap border-t border-gray-700/40 px-3 py-2 text-xs text-gray-400">
          {text}
        </div>
      )}
    </div>
  )
}
