/**
 * Celery 任务方框悬停详情（服务状态页 CeleryQueuesCard 与智能中枢主板任务方框共用），
 * 状态文案/耗时格式单点维护，两处悬浮内容保持一致。
 */
import type { CeleryTaskState, CeleryTaskSquare } from '@ai-invest/shared'

import { formatDateTime } from '@/utils/formatters'

const STATE_TEXT: Record<CeleryTaskState, string> = {
  pending: '排队中',
  running: '执行中',
  success: '已完成',
  partial: '部分成功',
  failed: '失败',
  skipped: '已跳过',
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.round((ms % 60_000) / 1000)
  return `${minutes}m${String(seconds).padStart(2, '0')}s`
}

export function CeleryTaskTooltipContent({ task }: { task: CeleryTaskSquare }) {
  return (
    <div className="max-w-80 space-y-1 text-xs">
      <div className="font-medium">{task.label}</div>
      <div className="opacity-80">
        {STATE_TEXT[task.state]}
        {task.source ? ` · ${task.source}` : ''}
        {task.durationMs != null ? ` · 耗时 ${formatDuration(task.durationMs)}` : ''}
      </div>
      {task.startedAt && <div className="opacity-60">开始 {formatDateTime(task.startedAt)}</div>}
      {task.finishedAt && <div className="opacity-60">结束 {formatDateTime(task.finishedAt)}</div>}
      {task.detail && <div className="opacity-80">{task.detail}</div>}
    </div>
  )
}
