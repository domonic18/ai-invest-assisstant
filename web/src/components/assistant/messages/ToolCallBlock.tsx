import { Button } from 'antd'
import { LoadingOutlined, SearchOutlined, ToolOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAssistantStore } from '@/stores/assistant'

import { parsePageEvent } from '../pageEvents'
import { extractEventMarker } from '../runtimeUtils'

interface ToolCallBlockProps {
  toolName: string
  args: unknown
  result?: unknown
}

export function ToolCallBlock({ toolName, args, result }: ToolCallBlockProps) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const isRunning = result == null
  // 工具结果携带已注册的页面回写事件（__event__）时渲染查看按钮：
  // 重设 pageResult 并按注册表 path 导航到结果页（无论当前在哪个页面），
  // 目标页由 usePageAssistantResult 消费事件完成刷新与提示，随后收起侧边栏露出页面内容
  const pageAction = (() => {
    if (isRunning) return null
    const event = extractEventMarker(result)
    if (!event) return null
    return parsePageEvent(event)
  })()

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
      {pageAction && (
        <div className="border-t border-sky-900/40 px-3 py-2">
          <Button
            size="small"
            type="primary"
            ghost
            icon={<SearchOutlined />}
            onClick={() => {
              const store = useAssistantStore.getState()
              store.setPageResult(pageAction.result)
              store.closePanel()
              navigate(pageAction.path)
            }}
          >
            {pageAction.actionLabel}
          </Button>
        </div>
      )}
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
