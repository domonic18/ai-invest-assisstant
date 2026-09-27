import { ReloadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Skeleton, Tag, Tooltip, Typography, theme } from 'antd'
import type { CeleryQueueStatus, CeleryTaskSquare, CeleryTaskState } from '@ai-invest/shared'

import { useCeleryQueues } from '@/hooks/useCeleryQueues'
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

function stateColor(state: CeleryTaskState, token: ReturnType<typeof theme.useToken>['token']): string {
  switch (state) {
    case 'running':
      return token.colorPrimary
    case 'pending':
      return token.colorTextQuaternary
    case 'success':
      return token.colorSuccess
    case 'partial':
      return token.colorWarning
    case 'failed':
      return token.colorError
    case 'skipped':
      return token.colorSuccess
  }
}

function TaskTooltipContent({ task }: { task: CeleryTaskSquare }) {
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

function TaskSquare({ task }: { task: CeleryTaskSquare }) {
  const { token } = theme.useToken()
  const color = stateColor(task.state, token)
  const opacity = task.state === 'skipped' ? 0.45 : 1

  return (
    <Tooltip title={<TaskTooltipContent task={task} />}>
      <span
        data-testid={`task-${task.key}`}
        className="flex h-2.5 w-2.5 flex-none cursor-default items-center justify-center"
        style={{ opacity }}
      >
        {task.state === 'running' ? (
          <span
            className="h-2.5 w-2.5 animate-spin rounded-full border-[1.5px] border-solid"
            style={{ borderColor: `${color} transparent ${color} ${color}` }}
          />
        ) : (
          <span className="h-2.5 w-2.5 rounded-[2px]" style={{ backgroundColor: color }} />
        )}
      </span>
    </Tooltip>
  )
}

function Legend({ token }: { token: ReturnType<typeof theme.useToken>['token'] }) {
  const entries: Array<[CeleryTaskState, string]> = [
    ['pending', '排队中'],
    ['running', '执行中'],
    ['success', '已完成'],
    ['partial', '部分成功'],
    ['failed', '失败'],
    ['skipped', '已跳过'],
  ]
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      {entries.map(([state, text]) => (
        <span key={state} className="flex items-center gap-1.5">
          <span
            className="inline-block h-2 w-2 rounded-[2px]"
            style={{ backgroundColor: stateColor(state, token) }}
          />
          <Typography.Text type="secondary" className="!text-xs">
            {text}
          </Typography.Text>
        </span>
      ))}
    </div>
  )
}

function QueuePanel({ queue }: { queue: CeleryQueueStatus }) {
  const runningCount = queue.tasks.filter((t) => t.state === 'running').length
  const sampledPending = queue.tasks.filter((t) => t.state === 'pending').length
  const overflow = queue.pendingTotal - sampledPending
  const countText =
    runningCount > 0
      ? `执行中 ${runningCount} · 排队 ${queue.pendingTotal}`
      : `排队 ${queue.pendingTotal}`

  return (
    <Card variant="borderless" size="small">
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Typography.Text strong>{queue.label}</Typography.Text>
          <Tag style={{ fontFamily: 'monospace', marginInlineEnd: 0 }} className="!text-xs">
            {queue.name}
          </Tag>
        </div>
        <Typography.Text type="secondary" className="!text-xs">
          {countText}
        </Typography.Text>
      </div>
      {queue.tasks.length === 0 ? (
        <Typography.Text type="secondary" className="!text-xs">
          暂无任务
        </Typography.Text>
      ) : (
        <div className="flex flex-wrap items-center gap-1">
          {queue.tasks.map((task) => (
            <TaskSquare key={task.key} task={task} />
          ))}
          {overflow > 0 && (
            <Typography.Text type="secondary" className="!text-xs">
              +{overflow}
            </Typography.Text>
          )}
        </div>
      )}
    </Card>
  )
}

export function CeleryQueuesCard() {
  const { token } = theme.useToken()
  const { data, isLoading, error, refetch, isFetching } = useCeleryQueues()

  return (
    <Card
      variant="borderless"
      title={
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span>Celery 任务队列</span>
          <Button
            size="small"
            icon={<ReloadOutlined spin={isFetching} />}
            onClick={() => refetch()}
          >
            刷新
          </Button>
        </div>
      }
    >
      {isLoading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : error || !data ? (
        <Alert
          type="error"
          showIcon
          message="队列状态加载失败"
          description={error instanceof Error ? error.message : undefined}
          action={
            <Button size="small" danger onClick={() => refetch()}>
              重试
            </Button>
          }
        />
      ) : (
        <div className="space-y-4">
          {!data.brokerOk && (
            <Alert type="warning" showIcon message="Broker 不可达，排队任务数据不可用（仅展示数据库侧状态）" />
          )}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {data.queues.map((queue) => (
              <QueuePanel key={queue.name} queue={queue} />
            ))}
          </div>
          <Legend token={token} />
          <Typography.Text type="secondary" className="!text-xs">
            有任务执行时每 3 秒自动刷新，空闲时每 10 秒 · 最后更新 {formatDateTime(data.checkedAt)}
          </Typography.Text>
        </div>
      )}
    </Card>
  )
}
