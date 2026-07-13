import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiFundFlowResponse, ApiPaginatedResponse } from '@ai-invest/shared'

import { apiClient } from './client'
import { mapFundFlowData, mapPaginatedResponse } from './mappers'

export interface FundFlowParams {
  stockCode?: string
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

export async function fetchFundFlow(params: FundFlowParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiFundFlowResponse>>(
    ENDPOINTS.fundFlow.list,
    {
      params: {
        stock_code: params.stockCode,
        start_date: params.startDate,
        end_date: params.endDate,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    }
  )
  return mapPaginatedResponse(response.data, mapFundFlowData)
}
