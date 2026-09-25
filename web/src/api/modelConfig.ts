import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAsrConfig,
  ApiAsrConfigTestResult,
  ApiAsrConfigUpdateRequest,
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

// ---- ASR 渠道（社媒与知识库转写共用）----

export async function fetchAsrConfig(): Promise<ApiAsrConfig> {
  const response = await apiClient.get<ApiAsrConfig>(ENDPOINTS.admin.asrConfig)
  return response.data
}

export async function updateAsrConfig(
  data: ApiAsrConfigUpdateRequest,
): Promise<ApiAsrConfig> {
  const response = await apiClient.put<ApiAsrConfig>(ENDPOINTS.admin.asrConfig, data)
  return response.data
}

export async function testAsrConfig(): Promise<ApiAsrConfigTestResult> {
  const response = await apiClient.post<ApiAsrConfigTestResult>(ENDPOINTS.admin.asrConfigTest)
  return response.data
}
