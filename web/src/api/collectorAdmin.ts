import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiCollectorLogResponse,
  ApiCollectorRunResponse,
  ApiCollectorTaskCatalogResponse,
  ApiCollectorTaskChannelsResponse,
  ApiCollectorTaskRunRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export interface CollectorLogFilters {
  taskName?: string | null
  source?: string | null
}

export async function fetchCollectorLogs(
  limit = 50,
  filters: CollectorLogFilters = {},
): Promise<ApiCollectorLogResponse[]> {
  const { data } = await apiClient.get(ENDPOINTS.admin.collectorLogs, {
    params: {
      limit,
      task_name: filters.taskName || undefined,
      source: filters.source || undefined,
    },
  })
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
