import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAdminReportCreateRequest,
  ApiAdminReportResponse,
  ApiAdminReportUpdateRequest,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminReport, mapPaginatedResponse } from './mappers'

export interface AdminReportParams {
  stockCode?: string
  fileType?: string
  page?: number
  pageSize?: number
}

export async function fetchAdminReports(params: AdminReportParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiAdminReportResponse>>(
    ENDPOINTS.admin.reports,
    {
      params: {
        stock_code: params.stockCode,
        file_type: params.fileType,
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    },
  )
  return mapPaginatedResponse(response.data, mapAdminReport)
}

export async function createAdminReport(data: ApiAdminReportCreateRequest) {
  const response = await apiClient.post<ApiAdminReportResponse>(
    ENDPOINTS.admin.reports,
    data,
  )
  return mapAdminReport(response.data)
}

export async function updateAdminReport(
  id: number,
  data: ApiAdminReportUpdateRequest,
) {
  const response = await apiClient.put<ApiAdminReportResponse>(
    ENDPOINTS.admin.report(id),
    data,
  )
  return mapAdminReport(response.data)
}

export async function deleteAdminReport(id: number) {
  await apiClient.delete(ENDPOINTS.admin.report(id))
}
