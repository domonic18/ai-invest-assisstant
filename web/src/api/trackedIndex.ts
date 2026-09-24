import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiTrackedIndexOption } from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchTrackedIndexOptions(): Promise<ApiTrackedIndexOption[]> {
  const response = await apiClient.get<ApiTrackedIndexOption[]>(
    ENDPOINTS.market.trackedIndexOptions,
  )
  return response.data
}

export interface TrackedIndexCreateData {
  indexCode: string
  indexName: string
  marketCategory: string
  dataSource: string
}

export async function createTrackedIndex(data: TrackedIndexCreateData): Promise<void> {
  await apiClient.post(ENDPOINTS.admin.trackedIndexes, { ...data, isEnabled: true })
}

export async function deleteTrackedIndex(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.trackedIndex(id))
}
