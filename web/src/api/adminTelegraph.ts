import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAdminTelegraphResponse,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminTelegraph, mapPaginatedResponse } from './mappers'

export interface AdminTelegraphParams {
  q?: string
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

export async function fetchAdminTelegraph(params: AdminTelegraphParams = {}) {
  const response = await apiClient.get<
    ApiPaginatedResponse<ApiAdminTelegraphResponse>
  >(ENDPOINTS.admin.telegraph, {
    params: {
      q: params.q,
      start_date: params.startDate,
      end_date: params.endDate,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  })
  return mapPaginatedResponse(response.data, mapAdminTelegraph)
}

export async function deleteAdminTelegraph(id: number) {
  await apiClient.delete(ENDPOINTS.admin.telegraphItem(id))
}

export async function batchDeleteAdminTelegraph(ids: number[]) {
  const response = await apiClient.post<{ deleted: number }>(
    ENDPOINTS.admin.telegraphBatchDelete,
    { ids },
  )
  return response.data.deleted
}
