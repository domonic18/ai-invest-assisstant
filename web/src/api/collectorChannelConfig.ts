import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiCollectorChannelConfigCreateRequest,
  ApiCollectorChannelConfigResponse,
  ApiCollectorChannelConfigUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchCollectorChannelConfigs(): Promise<ApiCollectorChannelConfigResponse[]> {
  const { data } = await apiClient.get<ApiCollectorChannelConfigResponse[]>(
    ENDPOINTS.admin.collectorChannels,
  )
  return data
}

export async function createCollectorChannelConfig(
  data: ApiCollectorChannelConfigCreateRequest,
): Promise<ApiCollectorChannelConfigResponse> {
  const { data: response } = await apiClient.post<ApiCollectorChannelConfigResponse>(
    ENDPOINTS.admin.collectorChannels,
    data,
  )
  return response
}

export async function updateCollectorChannelConfig(
  id: number,
  data: ApiCollectorChannelConfigUpdateRequest,
): Promise<ApiCollectorChannelConfigResponse> {
  const { data: response } = await apiClient.put<ApiCollectorChannelConfigResponse>(
    ENDPOINTS.admin.collectorChannel(id),
    data,
  )
  return response
}

export async function deleteCollectorChannelConfig(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.collectorChannel(id))
}
