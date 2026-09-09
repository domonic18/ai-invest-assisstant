import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiProxyConfigCreateRequest,
  ApiProxyConfigResponse,
  ApiProxyConfigTestResponse,
  ApiProxyConfigUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchProxyConfigs(): Promise<ApiProxyConfigResponse[]> {
  const response = await apiClient.get<ApiProxyConfigResponse[]>(ENDPOINTS.admin.proxyConfigs)
  return response.data
}

export async function createProxyConfig(
  data: ApiProxyConfigCreateRequest,
): Promise<ApiProxyConfigResponse> {
  const response = await apiClient.post<ApiProxyConfigResponse>(ENDPOINTS.admin.proxyConfigs, data)
  return response.data
}

export async function updateProxyConfig(
  id: number,
  data: ApiProxyConfigUpdateRequest,
): Promise<ApiProxyConfigResponse> {
  const response = await apiClient.put<ApiProxyConfigResponse>(
    ENDPOINTS.admin.proxyConfig(id),
    data,
  )
  return response.data
}

export async function deleteProxyConfig(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.proxyConfig(id))
}

export async function testProxyConfig(id: number): Promise<ApiProxyConfigTestResponse> {
  const response = await apiClient.post<ApiProxyConfigTestResponse>(
    ENDPOINTS.admin.testProxyConfig(id),
  )
  return response.data
}
