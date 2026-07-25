import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiFinancialReportCollectLogResponse,
  ApiFinancialReportCollectRequest,
  ApiFinancialReportCollectResponse,
  ApiFinancialReportResponse,
  ApiFinancialSummarizeResponse,
  ApiPaginatedResponse,
  FinancialReport,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapPaginatedResponse } from './mappers'

export interface FinancialReportParams {
  stockCode?: string
  q?: string
  reportType?: string
  startDate?: string
  endDate?: string
  page?: number
  pageSize?: number
}

function mapFinancialReport(dto: ApiFinancialReportResponse): FinancialReport {
  return {
    id: dto.id,
    stockCode: dto.stock_code,
    stockName: dto.stock_name,
    title: dto.title,
    reportType: dto.report_type,
    reportDate: dto.report_date,
    fileSize: dto.file_size,
    summary: dto.summary,
    hasSummary: dto.has_summary,
    createdAt: dto.created_at,
  }
}

export async function fetchFinancialReports(params: FinancialReportParams = {}) {
  const response = await apiClient.get<
    ApiPaginatedResponse<ApiFinancialReportResponse>
  >(ENDPOINTS.financialReports.list, {
    params: {
      stock_code: params.stockCode,
      q: params.q,
      report_type: params.reportType,
      start_date: params.startDate,
      end_date: params.endDate,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  })
  return mapPaginatedResponse(response.data, mapFinancialReport)
}

export async function fetchFinancialReportPdfUrl(
  id: number | string,
): Promise<string> {
  const response = await apiClient.get<{ url: string }>(
    ENDPOINTS.financialReports.pdfUrl(id),
  )
  return response.data.url
}

export async function summarizeFinancialReport(id: number | string) {
  const response = await apiClient.post<ApiFinancialSummarizeResponse>(
    ENDPOINTS.financialReports.summarize(id),
  )
  return response.data
}

export async function collectFinancialReport(
  body: ApiFinancialReportCollectRequest,
) {
  const response = await apiClient.post<ApiFinancialReportCollectResponse>(
    ENDPOINTS.financialReports.collect,
    body,
  )
  return response.data
}

export async function fetchFinancialReportCollectLog(logId: number | string) {
  const response = await apiClient.get<ApiFinancialReportCollectLogResponse>(
    ENDPOINTS.financialReports.collectLog(logId),
  )
  return response.data
}
