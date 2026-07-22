import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiIndexAuctionTrendResponse } from '@ai-invest/shared'

import { apiClient } from './client'

export type IndexAuctionTrend = ApiIndexAuctionTrendResponse

export interface IndexAuctionTrendParams {
  days?: number
  startDate?: string
  endDate?: string
}

export async function fetchIndexAuctionTrend(
  params: IndexAuctionTrendParams = {},
): Promise<IndexAuctionTrend> {
  const { days = 30, startDate, endDate } = params
  const response = await apiClient.get<ApiIndexAuctionTrendResponse>(
    ENDPOINTS.auction.indexTrend(days, startDate, endDate),
  )
  return response.data
}
