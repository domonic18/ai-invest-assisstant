import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAdminNewsCreateRequest,
  ApiAdminNewsResponse,
  ApiAdminNewsUpdateRequest,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminNews, mapPaginatedResponse } from './mappers'

export interface AdminNewsParams {
  stockCode?: string
  docType?: string
  q?: string
  page?: number
  pageSize?: number
}

export async function fetchAdminNews(params: AdminNewsParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiAdminNewsResponse>>(
    ENDPOINTS.admin.news,
    {
      params: {
        stock_code: params.stockCode,
        doc_type: params.docType,
        q: params.q,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    },
  )
  return mapPaginatedResponse(response.data, mapAdminNews)
}

export async function createAdminNews(data: ApiAdminNewsCreateRequest) {
  const response = await apiClient.post<ApiAdminNewsResponse>(
    ENDPOINTS.admin.news,
    data,
  )
  return mapAdminNews(response.data)
}

export async function updateAdminNews(
  id: number,
  data: ApiAdminNewsUpdateRequest,
) {
  const response = await apiClient.put<ApiAdminNewsResponse>(
    ENDPOINTS.admin.newsItem(id),
    data,
  )
  return mapAdminNews(response.data)
}

export async function deleteAdminNews(id: number) {
  await apiClient.delete(ENDPOINTS.admin.newsItem(id))
}
