/** Celery collector constants shared between frontend and backend. */
export const CollectorStatus = {
  PENDING: 'pending',
  RUNNING: 'running',
  SUCCESS: 'success',
  FAILED: 'failed',
  PARTIAL: 'partial',
} as const

export type CollectorStatus = (typeof CollectorStatus)[keyof typeof CollectorStatus]

export const CollectorQueue = {
  REALTIME: 'collector.realtime',
  BATCH: 'collector.batch',
  HEAVY: 'collector.heavy',
} as const

export type CollectorQueue = (typeof CollectorQueue)[keyof typeof CollectorQueue]

export const CollectorMode = {
  BEAT: 'beat',
  WORKER: 'worker',
} as const

export type CollectorMode = (typeof CollectorMode)[keyof typeof CollectorMode]
