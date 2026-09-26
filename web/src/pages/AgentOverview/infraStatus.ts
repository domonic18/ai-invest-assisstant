/**
 * 基建层状态映射纯函数（D33）：system status items → 五盒状态
 * （celery 取 broker+workers 双 up）+ Celery 任务方框合并口径
 * （running 优先 + 最近终态，与后端 _fetch_log_rows 一致）。
 */
import type { CeleryQueues, CeleryTaskSquare, CeleryTaskState, ServiceStatusItem } from '@ai-invest/shared'

import type { InfraId } from './hubLayout'

export const TASK_STATE_META: Record<CeleryTaskState, { color: string; text: string }> = {
  running: { color: '#1677ff', text: '运行中' },
  pending: { color: '#8c8c8c', text: '排队中' },
  success: { color: '#52c41a', text: '成功' },
  partial: { color: '#faad14', text: '部分成功' },
  failed: { color: '#ff4d4f', text: '失败' },
  skipped: { color: '#8c8c8c', text: '跳过' },
}

/** system status items → 基建五盒状态（celery 取 broker+workers 双 up）。 */
export function mapInfraStatus(
  items: ServiceStatusItem[] | undefined,
): Record<InfraId, ServiceStatusItem | null> {
  const byKey = new Map((items ?? []).map((item) => [item.key, item]))
  const broker = byKey.get('celery-broker')
  const workers = byKey.get('celery-workers')
  const celery: ServiceStatusItem | null =
    broker && workers
      ? {
          key: 'celery',
          name: 'Celery',
          category: 'compute',
          status: broker.status === 'up' && workers.status === 'up' ? 'up' : 'down',
          latencyMs: null,
          detail: `${broker.name} ${broker.status} · ${workers.name} ${workers.status}`,
          error: null,
        }
      : null
  return {
    postgres: byKey.get('postgres') ?? null,
    redis: byKey.get('redis') ?? null,
    celery,
    counter: byKey.get('paper-trade') ?? null,
    minio: byKey.get('minio') ?? null,
  }
}

/** 三队列任务合并为方框流：running 优先（started 倒序）→ 最近终态。 */
export function mergeTaskSquares(queues: CeleryQueues | undefined): CeleryTaskSquare[] {
  const running = (queues?.queues ?? []).flatMap((q) => q.tasks.filter((t) => t.state === 'running'))
  const terminal = (queues?.queues ?? []).flatMap(
    (q) => q.tasks.filter((t) => t.state !== 'running'),
  )
  const byTime = (a: CeleryTaskSquare, b: CeleryTaskSquare) =>
    (b.finishedAt ?? b.startedAt ?? '').localeCompare(a.finishedAt ?? a.startedAt ?? '')
  running.sort((a, b) => (b.startedAt ?? '').localeCompare(a.startedAt ?? ''))
  terminal.sort(byTime)
  return [...running, ...terminal]
}
