import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAdminStockCreateRequest,
  ApiAdminStockResponse,
  ApiAdminStockUpdateRequest,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminStock, mapPaginatedResponse } from './mappers'

export interface AdminStockParams {
  q?: string
  page?: number
  pageSize?: number
}

export async function fetchAdminStocks(params: AdminStockParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiAdminStockResponse>>(
    ENDPOINTS.admin.stocks,
    {
      params: {
        q: params.q,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    },
  )
  return mapPaginatedResponse(response.data, mapAdminStock)
}

export async function createAdminStock(data: ApiAdminStockCreateRequest) {
  const response = await apiClient.post<ApiAdminStockResponse>(
    ENDPOINTS.admin.stocks,
    data,
  )
  return mapAdminStock(response.data)
}

export async function updateAdminStock(
  id: number,
  data: ApiAdminStockUpdateRequest,
) {
  const response = await apiClient.put<ApiAdminStockResponse>(
    ENDPOINTS.admin.stock(id),
    data,
  )
  return mapAdminStock(response.data)
}

export async function deleteAdminStock(id: number) {
  await apiClient.delete(ENDPOINTS.admin.stock(id))
}
