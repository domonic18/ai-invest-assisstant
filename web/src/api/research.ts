import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiPaginatedResponse,
  ApiResearchReportResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapPaginatedResponse, mapResearchReport } from './mappers'

export interface ResearchParams {
  stockCode?: string
  q?: string
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

export async function fetchResearchReports(params: ResearchParams = {}) {
  const response = await apiClient.get<
    ApiPaginatedResponse<ApiResearchReportResponse>
  >(ENDPOINTS.research.list, {
    params: {
      stock_code: params.stockCode,
      q: params.q,
      start_date: params.startDate,
      end_date: params.endDate,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  })
  return mapPaginatedResponse(response.data, mapResearchReport)
}

export async function fetchResearchReportDetail(id: number | string) {
  const response = await apiClient.get<ApiResearchReportResponse>(
    ENDPOINTS.research.detail(id),
  )
  return mapResearchReport(response.data)
}

export async function summarizeResearchReport(id: number | string) {
  const response = await apiClient.post<{ summary: string }>(
    ENDPOINTS.research.summarize(id),
  )
  return response.data.summary
}
