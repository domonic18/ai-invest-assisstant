import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiPaginatedResponse,
  ApiResearchReportFiltersResponse,
  ApiResearchReportResponse,
  ApiResearchSummarizeResponse,
  ResearchReportFilterOptions,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapPaginatedResponse, mapResearchReport } from './mappers'

export interface ResearchParams {
  stockCode?: string
  q?: string
  broker?: string
  industry?: string
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
      broker: params.broker,
      industry: params.industry,
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

export async function fetchResearchFilters(): Promise<ResearchReportFilterOptions> {
  const response = await apiClient.get<ApiResearchReportFiltersResponse>(
    ENDPOINTS.research.filters,
  )
  return { brokers: response.data.brokers, industries: response.data.industries }
}

export async function fetchResearchPdfUrl(id: number | string): Promise<string> {
  const response = await apiClient.get<{ url: string }>(
    ENDPOINTS.research.pdfUrl(id),
  )
  return response.data.url
}

export async function summarizeResearchReport(id: number | string) {
  const response = await apiClient.post<ApiResearchSummarizeResponse>(
    ENDPOINTS.research.summarize(id),
  )
  return response.data
}
