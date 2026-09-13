import { ENDPOINTS } from '@ai-invest/shared'
import type { CollectorChannelDebugRequest, CollectorChannelDebugResult } from '@ai-invest/shared'

import { apiClient } from './client'

export async function debugCollectorChannel(
  id: number,
  data: CollectorChannelDebugRequest,
): Promise<CollectorChannelDebugResult> {
  const response = await apiClient.post<CollectorChannelDebugResult>(
    ENDPOINTS.admin.collectorChannelDebug(id),
    data,
  )
  return response.data
}
