import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiCollectorLogResponse,
  ApiCollectorLogSummaryResponse,
  ApiCollectorRunResponse,
  ApiCollectorTaskCatalogResponse,
  ApiCollectorTaskChannelsResponse,
  ApiCollectorTaskRunRequest,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

export interface CollectorLogFilters {
  page?: number
  pageSize?: number
  taskName?: string | null
  source?: string | null
  status?: string | null
  /** 业务日期（YYYY-MM-DD，Asia/Shanghai 日历日），闭区间。 */
  startDate?: string | null
  endDate?: string | null
}

export async function fetchCollectorLogs(
  filters: CollectorLogFilters = {},
): Promise<ApiPaginatedResponse<ApiCollectorLogResponse>> {
  const { data } = await apiClient.get<ApiPaginatedResponse<ApiCollectorLogResponse>>(
    ENDPOINTS.admin.collectorLogs,
    {
      params: {
        page: filters.page ?? 1,
        page_size: filters.pageSize ?? 20,
        task_name: filters.taskName || undefined,
        source: filters.source || undefined,
        status: filters.status || undefined,
        start_date: filters.startDate || undefined,
        end_date: filters.endDate || undefined,
      },
    },
  )
  return data
}

export async function fetchCollectorLogSummary(): Promise<ApiCollectorLogSummaryResponse> {
  const { data } = await apiClient.get<ApiCollectorLogSummaryResponse>(
    ENDPOINTS.admin.collectorLogSummary,
  )
  return data
}

export async function fetchCollectorTaskCatalog(): Promise<ApiCollectorTaskCatalogResponse> {
  const { data } = await apiClient.get<ApiCollectorTaskCatalogResponse>(
    ENDPOINTS.admin.collectorTaskCatalog,
  )
  return data
}

export async function fetchCollectorTaskChannels(
  taskName: string,
): Promise<ApiCollectorTaskChannelsResponse> {
  const { data } = await apiClient.get<ApiCollectorTaskChannelsResponse>(
    ENDPOINTS.admin.collectorTaskChannels(taskName),
  )
  return data
}

export async function runCollectorTask(
  taskName: string,
  body: ApiCollectorTaskRunRequest = {},
): Promise<ApiCollectorRunResponse> {
  const { data } = await apiClient.post<ApiCollectorRunResponse>(
    ENDPOINTS.admin.runCollectorTask(taskName),
    body,
  )
  return data
}
