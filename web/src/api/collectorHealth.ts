import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiCollectorChannelHealthItem,
  ApiCollectorClearSnapshotsResponse,
  ApiCollectorHealthOverview,
  ApiCollectorHealthTaskItem,
  ApiCollectorRunHealthCheckResponse,
  ApiCollectorScheduleCheckResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

export interface HealthTaskFilters {
  domain?: string | null
  status?: string | null
}

export async function fetchHealthOverview(): Promise<ApiCollectorHealthOverview> {
  const { data } = await apiClient.get<ApiCollectorHealthOverview>(
    ENDPOINTS.admin.collectorHealthOverview,
  )
  return data
}

export async function fetchHealthTasks(
  filters: HealthTaskFilters = {},
): Promise<ApiCollectorHealthTaskItem[]> {
  const { data } = await apiClient.get<ApiCollectorHealthTaskItem[]>(
    ENDPOINTS.admin.collectorHealthTasks,
    { params: { domain: filters.domain || undefined, status: filters.status || undefined } },
  )
  return data
}

export async function fetchHealthChannels(): Promise<ApiCollectorChannelHealthItem[]> {
  const { data } = await apiClient.get<ApiCollectorChannelHealthItem[]>(
    ENDPOINTS.admin.collectorHealthChannels,
  )
  return data
}

export async function fetchHealthScheduleCheck(
  date: string,
): Promise<ApiCollectorScheduleCheckResponse> {
  const { data } = await apiClient.get<ApiCollectorScheduleCheckResponse>(
    ENDPOINTS.admin.collectorHealthScheduleCheck,
    { params: { date } },
  )
  return data
}

export async function runHealthCheck(): Promise<ApiCollectorRunHealthCheckResponse> {
  const { data } = await apiClient.post<ApiCollectorRunHealthCheckResponse>(
    ENDPOINTS.admin.collectorHealthRun,
  )
  return data
}

export async function clearHealthSnapshots(filters: {
  taskType?: string | null
  source?: string | null
} = {}): Promise<ApiCollectorClearSnapshotsResponse> {
  const { data } = await apiClient.delete<ApiCollectorClearSnapshotsResponse>(
    ENDPOINTS.admin.collectorHealthSnapshots,
    {
      params: {
        task_type: filters.taskType || undefined,
        source: filters.source || undefined,
      },
    },
  )
  return data
}
