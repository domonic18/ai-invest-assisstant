import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiNewsChannelsResponse } from '@ai-invest/shared'

import { apiClient } from './client'

/** 渠道监控卡 + 今日统计（wire 与领域同构，直接透传 shared 类型）。 */
export async function fetchNewsChannels(): Promise<ApiNewsChannelsResponse> {
  const response = await apiClient.get<ApiNewsChannelsResponse>(
    ENDPOINTS.news.channels,
  )
  return response.data
}
