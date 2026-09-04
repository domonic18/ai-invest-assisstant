import { LoadingOutlined, ReloadOutlined, WarningFilled } from '@ant-design/icons'
import { Button, Tooltip } from 'antd'

import { panelColors } from '@/theme/colors'

export type LoadingStatus = 'idle' | 'loading' | 'error'

export interface LoadingTask {
  key: string
  label: string
  status: LoadingStatus
  onRetry?: () => void
}

interface StockLoadingStatusProps {
  tasks: LoadingTask[]
}

export function StockLoadingStatus({ tasks }: StockLoadingStatusProps) {
  const visible = tasks.filter((t) => t.status !== 'idle')
  if (visible.length === 0) return null

  const hasError = visible.some((t) => t.status === 'error')
  const allDone = visible.every((t) => t.status === 'error')

  return (
    <div
      className="px-3 py-2 space-y-1.5"
      style={{
        backgroundColor: hasError ? '#1a0e0e' : panelColors.bg,
        borderBottom: `1px solid ${panelColors.border}`,
      }}
    >
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-[#8c8c8c] tracking-wider">
          {allDone ? '部分数据加载失败' : '正在拉取数据'}
        </span>
        {hasError && (
          <Tooltip title="重新拉取全部失败项">
            <Button
              size="small"
              type="text"
              icon={<ReloadOutlined />}
              onClick={() => visible.forEach((t) => t.status === 'error' && t.onRetry?.())}
              className="!text-[#ff7875] !text-xs"
            >
              重试失败
            </Button>
          </Tooltip>
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {visible.map((task) => (
          <span key={task.key} className="inline-flex items-center gap-1 text-[11px]">
            {task.status === 'loading' && (
              <LoadingOutlined style={{ color: panelColors.textMuted }} />
            )}
            {task.status === 'error' && <WarningFilled className="text-[#ff7875]" />}
            <span
              className={
                task.status === 'loading'
                  ? 'text-[#d1d4dc]'
                  : task.status === 'error'
                    ? 'text-[#ff7875]'
                    : 'text-[#8c8c8c]'
              }
            >
              {task.label}
            </span>
            {task.status === 'error' && task.onRetry && (
              <Button
                size="small"
                type="text"
                icon={<ReloadOutlined />}
                onClick={task.onRetry}
                className="!p-0 !h-auto !text-[#ff7875]"
              />
            )}
          </span>
        ))}
      </div>
    </div>
  )
}
