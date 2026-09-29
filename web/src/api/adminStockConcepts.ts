import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAdminStockConceptCreateRequest,
  ApiAdminStockConceptResponse,
  ApiAdminStockConceptUpdateRequest,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminStockConcept, mapPaginatedResponse } from './mappers'

export interface AdminStockConceptParams {
  q?: string
  concept?: string
  page?: number
  pageSize?: number
}

export async function fetchAdminStockConcepts(params: AdminStockConceptParams = {}) {
  const response = await apiClient.get<
    ApiPaginatedResponse<ApiAdminStockConceptResponse>
  >(ENDPOINTS.admin.stockConcepts, {
    params: {
      q: params.q,
      concept: params.concept,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  })
  return mapPaginatedResponse(response.data, mapAdminStockConcept)
}

export async function createAdminStockConcept(
  data: ApiAdminStockConceptCreateRequest,
) {
  const response = await apiClient.post<ApiAdminStockConceptResponse>(
    ENDPOINTS.admin.stockConcepts,
    data,
  )
  return mapAdminStockConcept(response.data)
}

export async function updateAdminStockConcept(
  id: number,
  data: ApiAdminStockConceptUpdateRequest,
) {
  const response = await apiClient.put<ApiAdminStockConceptResponse>(
    ENDPOINTS.admin.stockConcept(id),
    data,
  )
  return mapAdminStockConcept(response.data)
}

export async function deleteAdminStockConcept(id: number) {
  await apiClient.delete(ENDPOINTS.admin.stockConcept(id))
}
