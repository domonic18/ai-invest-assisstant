import { ENDPOINTS } from '@ai-invest/shared'
import type { SystemStatus } from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const response = await apiClient.get<SystemStatus>(ENDPOINTS.admin.systemStatus)
  return response.data
}
