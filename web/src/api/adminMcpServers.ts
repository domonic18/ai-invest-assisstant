import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiMcpServerConfig,
  ApiMcpServerCreateRequest,
  ApiMcpServerTestResult,
  ApiMcpServerUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchMcpServers(): Promise<ApiMcpServerConfig[]> {
  const response = await apiClient.get<ApiMcpServerConfig[]>(ENDPOINTS.admin.mcpServers)
  return response.data
}

export async function createMcpServer(
  data: ApiMcpServerCreateRequest,
): Promise<ApiMcpServerConfig> {
  const response = await apiClient.post<ApiMcpServerConfig>(ENDPOINTS.admin.mcpServers, data)
  return response.data
}

export async function updateMcpServer(
  id: number,
  data: ApiMcpServerUpdateRequest,
): Promise<ApiMcpServerConfig> {
  const response = await apiClient.patch<ApiMcpServerConfig>(
    ENDPOINTS.admin.mcpServer(id),
    data,
  )
  return response.data
}

export async function deleteMcpServer(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.mcpServer(id))
}

export async function testMcpServer(id: number): Promise<ApiMcpServerTestResult> {
  const response = await apiClient.post<ApiMcpServerTestResult>(
    ENDPOINTS.admin.mcpServerTest(id),
  )
  return response.data
}

export async function testMcpServerDraft(
  data: ApiMcpServerCreateRequest,
): Promise<ApiMcpServerTestResult> {
  const response = await apiClient.post<ApiMcpServerTestResult>(
    ENDPOINTS.admin.mcpServerTestDraft,
    data,
  )
  return response.data
}
