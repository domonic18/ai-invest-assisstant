import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAuctionDataResponse,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAuctionData, mapPaginatedResponse } from './mappers'

export interface AuctionParams {
  tradeDate?: string
  page?: number
  pageSize?: number
}

export async function fetchAuctionData(code: string, params: AuctionParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiAuctionDataResponse>>(
    ENDPOINTS.auction.get(code),
    {
      params: {
        trade_date: params.tradeDate,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    },
  )
  return mapPaginatedResponse(response.data, mapAuctionData)
}
