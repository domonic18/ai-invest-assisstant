/** Common business statuses used across the application. */
export const Status = {
  PENDING: 'pending',
  RUNNING: 'running',
  SUCCESS: 'success',
  FAILED: 'failed',
  PARTIAL: 'partial',
} as const

export type Status = (typeof Status)[keyof typeof Status]
