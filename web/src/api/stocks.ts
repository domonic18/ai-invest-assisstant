import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiKlineDataResponse,
  ApiPaginatedResponse,
  ApiStockBasicResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapKlineData, mapPaginatedResponse, mapStock } from './mappers'

export interface SearchStocksParams {
  q: string
  limit?: number
}

export interface KlineParams {
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

export async function searchStocks(params: SearchStocksParams) {
  const response = await apiClient.get<ApiStockBasicResponse[]>(ENDPOINTS.stocks.search, {
    params: { q: params.q, limit: params.limit ?? 20 },
  })
  return response.data.map(mapStock)
}

export async function fetchStockDetail(code: string, market?: string) {
  const response = await apiClient.get<ApiStockBasicResponse>(ENDPOINTS.stocks.detail(code), {
    params: market ? { market } : undefined,
  })
  return mapStock(response.data)
}

export async function fetchKline(code: string, params: KlineParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiKlineDataResponse>>(
    ENDPOINTS.kline.get(code),
    {
      params: {
        start_date: params.startDate,
        end_date: params.endDate,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 100,
      },
    }
  )
  return mapPaginatedResponse(response.data, mapKlineData)
}
