import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiKey, ApiKeyCreateRequest, ApiKeyIssued } from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchMyApiKeys(): Promise<ApiKey[]> {
  const response = await apiClient.get<ApiKey[]>(ENDPOINTS.users.meApiKeys)
  return response.data
}

export async function createMyApiKey(
  data: ApiKeyCreateRequest,
): Promise<ApiKeyIssued> {
  const response = await apiClient.post<ApiKeyIssued>(
    ENDPOINTS.users.meApiKeys,
    data,
  )
  return response.data
}

export async function revokeMyApiKey(keyId: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.users.meApiKey(keyId))
}

export async function purgeMyApiKey(keyId: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.users.meApiKeyPurge(keyId))
}
