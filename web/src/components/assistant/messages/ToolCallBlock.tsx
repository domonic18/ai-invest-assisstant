import { LoadingOutlined, ToolOutlined } from '@ant-design/icons'
import { useState } from 'react'

interface ToolCallBlockProps {
  toolName: string
  args: unknown
  result?: unknown
}

export function ToolCallBlock({ toolName, args, result }: ToolCallBlockProps) {
  const [open, setOpen] = useState(false)
  const isRunning = result == null

  return (
    <div className="mb-2 overflow-hidden rounded-lg border border-sky-900/60 bg-sky-950/20">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs"
      >
        <ToolOutlined className="text-sky-400" />
        <span className="font-mono text-sky-300">{toolName}</span>
        <span className="ml-auto flex items-center gap-1 text-gray-400">
          {isRunning ? (
            <>
              <LoadingOutlined className="animate-spin" />
              运行中…
            </>
          ) : (
            '已完成'
          )}
        </span>
      </button>
      {open && (
        <div className="space-y-2 border-t border-sky-900/40 px-3 py-2 text-xs text-gray-300">
          <div>
            <span className="text-gray-500">参数：</span>
            <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-black/30 p-2">
              {JSON.stringify(args, null, 2)}
            </pre>
          </div>
          {!isRunning && (
            <div>
              <span className="text-gray-500">结果：</span>
              <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-black/30 p-2">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
