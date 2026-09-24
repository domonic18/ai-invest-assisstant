import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiKbSettingsResponse,
  ApiKbSettingsUpdateRequest,
  ApiKbSourceCreateRequest,
  ApiKbSourceResponse,
  ApiKbSourceUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

// ---- 知识库设置 ----

export async function fetchKbSettings(): Promise<ApiKbSettingsResponse> {
  const response = await apiClient.get<ApiKbSettingsResponse>(ENDPOINTS.admin.kbSettings)
  return response.data
}

export async function updateKbSettings(
  data: ApiKbSettingsUpdateRequest
): Promise<ApiKbSettingsResponse> {
  const response = await apiClient.put<ApiKbSettingsResponse>(
    ENDPOINTS.admin.kbSettings,
    data
  )
  return response.data
}

// ---- 知识源 ----

export async function fetchKbSources(): Promise<ApiKbSourceResponse[]> {
  const response = await apiClient.get<ApiKbSourceResponse[]>(ENDPOINTS.admin.kbSources)
  return response.data
}

export async function createKbSource(
  data: ApiKbSourceCreateRequest
): Promise<ApiKbSourceResponse> {
  const response = await apiClient.post<ApiKbSourceResponse>(ENDPOINTS.admin.kbSources, data)
  return response.data
}

export async function updateKbSource(
  id: number,
  data: ApiKbSourceUpdateRequest
): Promise<ApiKbSourceResponse> {
  const response = await apiClient.patch<ApiKbSourceResponse>(
    ENDPOINTS.admin.kbSource(id),
    data
  )
  return response.data
}

export async function deleteKbSource(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.kbSource(id))
}

export async function restoreKbSource(id: number): Promise<ApiKbSourceResponse> {
  const response = await apiClient.post<ApiKbSourceResponse>(
    ENDPOINTS.admin.kbSourceRestore(id)
  )
  return response.data
}
