import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiKbSettingsResponse,
  ApiKbSettingsUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchKbSettings(): Promise<ApiKbSettingsResponse> {
  const response = await apiClient.get<ApiKbSettingsResponse>(ENDPOINTS.admin.kbSettings)
  return response.data
}

export async function updateKbSettings(
  data: ApiKbSettingsUpdateRequest,
): Promise<ApiKbSettingsResponse> {
  const response = await apiClient.put<ApiKbSettingsResponse>(
    ENDPOINTS.admin.kbSettings,
    data,
  )
  return response.data
}
