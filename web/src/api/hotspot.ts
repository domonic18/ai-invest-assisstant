import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiPaginatedResponse,
  ApiSectorFundFlowResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapPaginatedResponse, mapSectorFundFlow } from './mappers'

export interface HotspotParams {
  sectorType?: string
  tradeDate?: string
  page?: number
  pageSize?: number
}

export async function fetchHotspots(params: HotspotParams = {}) {
  const response = await apiClient.get<
    ApiPaginatedResponse<ApiSectorFundFlowResponse>
  >(ENDPOINTS.hotspot.list, {
    params: {
      sector_type: params.sectorType,
      trade_date: params.tradeDate,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  })
  return mapPaginatedResponse(response.data, mapSectorFundFlow)
}
