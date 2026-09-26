/**
 * 基建层节点（D33）：五项核心状态灯盒（PostgreSQL/Redis/Celery/掘金柜台/
 * MinIO，system status 探测映射）+ Celery 任务方框条（复用系统状态页
 * celery-queues 的 running + 最近终态口径，状态色沿用 LAST_STATUS_META）。
 * 数据缺失降级「—」，不阻塞舞台其余层。状态映射纯函数见 infraStatus.ts。
 */
import {
  DatabaseOutlined,
  HddOutlined,
  LoadingOutlined,
  CloudServerOutlined,
  DeploymentUnitOutlined,
  TableOutlined,
} from '@ant-design/icons'
import { Tooltip } from 'antd'
import type { ReactNode } from 'react'

import type { CeleryTaskSquare, ServiceStatusItem, SystemStatus, CeleryQueues } from '@ai-invest/shared'

import { formatRelativeTime } from '@/utils/formatters'

import type { InfraId } from './hubLayout'
import type { Point } from './hubLayout'

import { TASK_STATE_META, mapInfraStatus, mergeTaskSquares } from './infraStatus'

const INFRA_META: Record<InfraId, { label: string; icon: ReactNode }> = {
  postgres: { label: 'PostgreSQL', icon: <DatabaseOutlined /> },
  redis: { label: 'Redis', icon: <CloudServerOutlined /> },
  celery: { label: 'Celery', icon: <DeploymentUnitOutlined /> },
  counter: { label: '掘金柜台', icon: <TableOutlined /> },
  minio: { label: 'MinIO', icon: <HddOutlined /> },
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

function TaskSquareChip({ square, point }: { square: CeleryTaskSquare; point: Point }) {
  const meta = TASK_STATE_META[square.state]
  const time = square.startedAt ?? square.finishedAt
  return (
    <Tooltip
      title={`${square.label} · ${meta.text}${square.durationMs != null ? ` · ${Math.round(square.durationMs / 1000)}s` : ''}${square.detail ? ` · ${square.detail}` : ''}`}
    >
      <div
        className="absolute w-[104px] -translate-x-1/2 -translate-y-1/2 rounded-md border border-white/10 bg-white/[0.03] px-1.5 py-1"
        style={{ left: point.x, top: point.y, borderLeft: `2px solid ${meta.color}` }}
      >
        <div className="flex items-center gap-1">
          {square.state === 'running' && (
            <LoadingOutlined style={{ color: meta.color, fontSize: 10 }} />
          )}
          <span className="truncate text-[10px] text-white/80">{square.label}</span>
        </div>
        <div className="mt-0.5 flex items-center justify-between text-[10px] leading-none">
          <span style={{ color: meta.color }}>{meta.text}</span>
          <span className="text-white/35">{time ? formatRelativeTime(time) : '—'}</span>
        </div>
      </div>
    </Tooltip>
  )
}

export function InfraLayerNodes({
  systemStatus,
  celeryQueues,
  points,
  squarePoints,
}: {
  systemStatus: SystemStatus | undefined
  celeryQueues: CeleryQueues | undefined
  points: Record<InfraId, Point>
  squarePoints: Point[]
}) {
  const status = mapInfraStatus(systemStatus?.items)
  const queueSummary = (celeryQueues?.queues ?? [])
    .map((q) => `${q.label} ${q.pendingTotal}`)
    .join(' · ')
  const squares = mergeTaskSquares(celeryQueues)
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
      {squares.slice(0, squarePoints.length).map((square, i) => (
        <TaskSquareChip key={square.key} square={square} point={squarePoints[i]} />
      ))}
    </>
  )
}
