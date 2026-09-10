import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiTrackedIndexOption } from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchTrackedIndexOptions(): Promise<ApiTrackedIndexOption[]> {
  const response = await apiClient.get<ApiTrackedIndexOption[]>(
    ENDPOINTS.market.trackedIndexOptions,
  )
  return response.data
}
