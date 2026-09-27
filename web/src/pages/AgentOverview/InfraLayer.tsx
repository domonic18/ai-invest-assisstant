/**
 * 基建层节点（D33）：五项核心状态灯盒（PostgreSQL/Redis/Celery/掘金柜台/
 * MinIO，system status 探测映射）+ Celery 队列分组任务方框（与系统状态页
 * CeleryQueuesCard 同口径：每队列一行任务小方框着状态色，hover 显示任务
 * 内容）。数据缺失降级「—」，不阻塞舞台其余层。状态映射纯函数见
 * infraStatus.ts。
 */
import {
  DatabaseOutlined,
  HddOutlined,
  CloudServerOutlined,
  DeploymentUnitOutlined,
  TableOutlined,
} from '@ant-design/icons'
import { Tooltip } from 'antd'
import type { ReactNode } from 'react'

import type {
  CeleryQueueStatus,
  CeleryTaskSquare,
  ServiceStatusItem,
  SystemStatus,
  CeleryQueues,
} from '@ai-invest/shared'

import { formatDateTime } from '@/utils/formatters'

import type { InfraId, Point } from './hubLayout'

import { TASK_STATE_META, mapInfraStatus } from './infraStatus'

const INFRA_META: Record<InfraId, { label: string; icon: ReactNode }> = {
  postgres: { label: 'PostgreSQL', icon: <DatabaseOutlined /> },
  redis: { label: 'Redis', icon: <CloudServerOutlined /> },
  celery: { label: 'Celery', icon: <DeploymentUnitOutlined /> },
  counter: { label: '掘金柜台', icon: <TableOutlined /> },
  minio: { label: 'MinIO', icon: <HddOutlined /> },
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.round((ms % 60_000) / 1000)
  return `${minutes}m${String(seconds).padStart(2, '0')}s`
}

function TaskTooltipContent({ task }: { task: CeleryTaskSquare }) {
  const meta = TASK_STATE_META[task.state]
  return (
    <div className="max-w-80 space-y-1 text-xs">
      <div className="font-medium">{task.label}</div>
      <div className="opacity-80">
        {meta.text}
        {task.source ? ` · ${task.source}` : ''}
        {task.durationMs != null ? ` · 耗时 ${formatDuration(task.durationMs)}` : ''}
      </div>
      {task.startedAt && <div className="opacity-60">开始 {formatDateTime(task.startedAt)}</div>}
      {task.finishedAt && <div className="opacity-60">结束 {formatDateTime(task.finishedAt)}</div>}
      {task.detail && <div className="opacity-80">{task.detail}</div>}
    </div>
  )
}

function TaskDot({ task }: { task: CeleryTaskSquare }) {
  const meta = TASK_STATE_META[task.state]
  const opacity = task.state === 'skipped' ? 0.45 : 1
  return (
    <Tooltip title={<TaskTooltipContent task={task} />}>
      <span
        className="flex size-2.5 flex-none cursor-default items-center justify-center"
        style={{ opacity }}
      >
        {task.state === 'running' ? (
          <span
            className="size-2.5 animate-spin rounded-full border-[1.5px] border-solid"
            style={{ borderColor: `${meta.color} transparent ${meta.color} ${meta.color}` }}
          />
        ) : (
          <span className="size-2.5 rounded-[2px]" style={{ backgroundColor: meta.color }} />
        )}
      </span>
    </Tooltip>
  )
}

function InfraBox({
  id,
  point,
  status,
  queueSummary,
}: {
  id: InfraId
  point: Point
  status: ServiceStatusItem | null
  queueSummary?: string
}) {
  const meta = INFRA_META[id]
  const up = status?.status === 'up'
  const dotColor = status == null ? '#595959' : up ? '#52c41a' : '#ff4d4f'
  return (
    <div
      className="absolute -translate-x-1/2 -translate-y-1/2"
      style={{ left: point.x, top: point.y }}
    >
      <Tooltip title={status ? `${meta.label} ${status.status}${status.detail ? ` · ${status.detail}` : ''}` : `${meta.label} 状态未知`}>
        <div className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-[#0b1220]/80 px-2.5 py-1.5 backdrop-blur-sm">
          <span className="text-sm text-white/70">{meta.icon}</span>
          <span className="leading-tight">
            <span className="flex items-center gap-1.5">
              <span className="inline-block size-1.5 rounded-full" style={{ backgroundColor: dotColor }} />
              <span className="text-xs text-white/85">{meta.label}</span>
              {status?.latencyMs != null && (
                <span className="font-mono text-[10px] text-white/40">{status.latencyMs}ms</span>
              )}
            </span>
            {queueSummary && <span className="block text-[10px] text-white/45">{queueSummary}</span>}
          </span>
        </div>
      </Tooltip>
    </div>
  )
}

function QueueGroup({ queue, point }: { queue: CeleryQueueStatus; point: Point }) {
  const runningCount = queue.tasks.filter((t) => t.state === 'running').length
  return (
    <div
      className="absolute flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1"
      style={{ left: point.x, top: point.y }}
    >
      <span className="whitespace-nowrap text-[10px] leading-none text-white/60">
        {queue.label}
        <span className="ml-1 text-white/35">
          {runningCount > 0 ? `执行中 ${runningCount} · 排队 ${queue.pendingTotal}` : `排队 ${queue.pendingTotal}`}
        </span>
      </span>
      {queue.tasks.length === 0 ? (
        <span className="text-[10px] leading-none text-white/30">暂无任务</span>
      ) : (
        <div className="flex items-center gap-1">
          {queue.tasks.map((task) => (
            <TaskDot key={task.key} task={task} />
          ))}
        </div>
      )}
    </div>
  )
}

export function InfraLayerNodes({
  systemStatus,
  celeryQueues,
  points,
  queuePoints,
}: {
  systemStatus: SystemStatus | undefined
  celeryQueues: CeleryQueues | undefined
  points: Record<InfraId, Point>
  queuePoints: Point[]
}) {
  const status = mapInfraStatus(systemStatus?.items)
  const queueSummary = (celeryQueues?.queues ?? [])
    .map((q) => `${q.label} ${q.pendingTotal}`)
    .join(' · ')
  const queues = celeryQueues?.queues ?? []
  return (
    <>
      {(Object.keys(INFRA_META) as InfraId[]).map((id) => (
        <InfraBox
          key={id}
          id={id}
          point={points[id]}
          status={status[id]}
          queueSummary={id === 'celery' ? queueSummary : undefined}
        />
      ))}
      {queues.slice(0, queuePoints.length).map((queue, i) => (
        <QueueGroup key={queue.name} queue={queue} point={queuePoints[i]} />
      ))}
    </>
  )
}
