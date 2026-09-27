import { ENDPOINTS } from '@ai-invest/shared'
import type { CeleryQueues, SystemStatus } from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const response = await apiClient.get<SystemStatus>(ENDPOINTS.admin.systemStatus)
  return response.data
}

export async function fetchCeleryQueues(): Promise<CeleryQueues> {
  const response = await apiClient.get<CeleryQueues>(ENDPOINTS.admin.celeryQueues)
  return response.data
}
