import axios from 'axios'

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiLlmConnectionTestResponse,
  ApiQuotaResponse,
  ApiUsageResponse,
  ApiUserLlmConfigResponse,
  ApiUserLlmConfigUpsertRequest,
  LlmConnectionTestResult,
  QuotaInfo,
  UsageSummary,
  UserLlmConfig,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchMyQuota(): Promise<QuotaInfo> {
  const response = await apiClient.get<ApiQuotaResponse>(ENDPOINTS.users.meQuota)
  return response.data
}

export async function fetchMyUsage(feature?: string): Promise<UsageSummary> {
  const response = await apiClient.get<ApiUsageResponse>(ENDPOINTS.users.meUsage, {
    params: feature ? { feature } : undefined,
  })
  return response.data
}

export async function fetchMyLlmConfig(): Promise<UserLlmConfig | null> {
  try {
    const response = await apiClient.get<ApiUserLlmConfigResponse>(
      ENDPOINTS.users.meLlmConfig,
    )
    return response.data
  } catch (error) {
    // 404 = 未配置（拦截器原地改写 message 但保留 response.status）
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null
    }
    throw error
  }
}

export async function saveMyLlmConfig(
  data: ApiUserLlmConfigUpsertRequest,
): Promise<UserLlmConfig> {
  const response = await apiClient.put<ApiUserLlmConfigResponse>(
    ENDPOINTS.users.meLlmConfig,
    data,
  )
  return response.data
}

export async function clearMyLlmConfig(): Promise<void> {
  await apiClient.delete(ENDPOINTS.users.meLlmConfig)
}

export async function testMyLlmConfig(
  data: ApiUserLlmConfigUpsertRequest,
): Promise<LlmConnectionTestResult> {
  const response = await apiClient.post<ApiLlmConnectionTestResponse>(
    ENDPOINTS.users.meLlmConfigTest,
    data,
  )
  return response.data
}
