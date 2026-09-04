import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiTrackedIndexCreateRequest,
  ApiTrackedIndexResponse,
  ApiTrackedIndexToggleResponse,
  ApiTrackedIndexUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchTrackedIndexes(): Promise<ApiTrackedIndexResponse[]> {
  const response = await apiClient.get<ApiTrackedIndexResponse[]>(
    ENDPOINTS.admin.trackedIndexes,
  )
  return response.data
}

export async function createTrackedIndex(
  data: ApiTrackedIndexCreateRequest,
): Promise<ApiTrackedIndexResponse> {
  const response = await apiClient.post<ApiTrackedIndexResponse>(
    ENDPOINTS.admin.trackedIndexes,
    data,
  )
  return response.data
}

export async function updateTrackedIndex(
  id: number,
  data: ApiTrackedIndexUpdateRequest,
): Promise<ApiTrackedIndexResponse> {
  const response = await apiClient.put<ApiTrackedIndexResponse>(
    ENDPOINTS.admin.trackedIndex(id),
    data,
  )
  return response.data
}

export async function deleteTrackedIndex(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.trackedIndex(id))
}

export async function toggleTrackedIndex(id: number): Promise<ApiTrackedIndexToggleResponse> {
  const response = await apiClient.patch<ApiTrackedIndexToggleResponse>(
    ENDPOINTS.admin.trackedIndexToggle(id),
  )
  return response.data
}
