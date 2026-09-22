import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiLLMConfigCreateRequest,
  ApiLLMConfigResponse,
  ApiLLMConfigTestResponse,
  ApiLLMConfigUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchLLMConfigs(): Promise<ApiLLMConfigResponse[]> {
  const response = await apiClient.get<ApiLLMConfigResponse[]>(ENDPOINTS.admin.llmConfigs)
  return response.data
}

export async function createLLMConfig(
  data: ApiLLMConfigCreateRequest,
): Promise<ApiLLMConfigResponse> {
  const response = await apiClient.post<ApiLLMConfigResponse>(ENDPOINTS.admin.llmConfigs, data)
  return response.data
}

export async function updateLLMConfig(
  id: number,
  data: ApiLLMConfigUpdateRequest,
): Promise<ApiLLMConfigResponse> {
  const response = await apiClient.put<ApiLLMConfigResponse>(
    ENDPOINTS.admin.llmConfig(id),
    data,
  )
  return response.data
}

export async function deleteLLMConfig(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.llmConfig(id))
}

export async function setDefaultLLMConfig(id: number): Promise<ApiLLMConfigResponse> {
  const response = await apiClient.post<ApiLLMConfigResponse>(
    ENDPOINTS.admin.setDefaultLLMConfig(id),
  )
  return response.data
}

export async function testLLMConfig(id: number): Promise<ApiLLMConfigTestResponse> {
  const response = await apiClient.post<ApiLLMConfigTestResponse>(
    ENDPOINTS.admin.testLLMConfig(id),
  )
  return response.data
}
