import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAsrConfig,
  ApiAsrConfigTestResult,
  ApiAsrConfigUpdateRequest,
  ApiSocialAccountAdmin,
  ApiSocialAccountCreateRequest,
  ApiSocialAccountsAdminPage,
  ApiSocialAccountUpdateRequest,
  ApiSocialBackfillResponse,
  ApiSocialCookieImportRequest,
  ApiSocialCookieImportResponse,
  ApiSocialPostDebug,
  ApiSocialStatus,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchSocialAccountsAdmin(
  page: number,
  pageSize: number,
): Promise<ApiSocialAccountsAdminPage> {
  const response = await apiClient.get<ApiSocialAccountsAdminPage>(
    ENDPOINTS.admin.socialAccounts,
    { params: { page, page_size: pageSize } },
  )
  return response.data
}

export async function createSocialAccount(
  data: ApiSocialAccountCreateRequest,
): Promise<ApiSocialAccountAdmin> {
  const response = await apiClient.post<ApiSocialAccountAdmin>(
    ENDPOINTS.admin.socialAccounts,
    data,
  )
  return response.data
}

export async function updateSocialAccount(
  id: number,
  data: ApiSocialAccountUpdateRequest,
): Promise<ApiSocialAccountAdmin> {
  const response = await apiClient.patch<ApiSocialAccountAdmin>(
    ENDPOINTS.admin.socialAccount(id),
    data,
  )
  return response.data
}

export async function deleteSocialAccount(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.socialAccount(id))
}

export async function backfillSocialAccount(
  id: number,
): Promise<ApiSocialBackfillResponse> {
  const response = await apiClient.post<ApiSocialBackfillResponse>(
    ENDPOINTS.admin.socialAccountBackfill(id),
  )
  return response.data
}

export async function fetchSocialStatus(): Promise<ApiSocialStatus> {
  const response = await apiClient.get<ApiSocialStatus>(ENDPOINTS.admin.socialStatus)
  return response.data
}

export async function fetchSocialAccountPosts(
  id: number,
): Promise<ApiSocialPostDebug[]> {
  const response = await apiClient.get<{ items: ApiSocialPostDebug[] }>(
    ENDPOINTS.admin.socialAccountPosts(id),
  )
  return response.data.items
}

export async function importSocialCookie(
  data: ApiSocialCookieImportRequest,
): Promise<ApiSocialCookieImportResponse> {
  const response = await apiClient.post<ApiSocialCookieImportResponse>(
    ENDPOINTS.admin.socialCookies,
    data,
  )
  return response.data
}

export async function fetchAsrConfig(): Promise<ApiAsrConfig> {
  const response = await apiClient.get<ApiAsrConfig>(ENDPOINTS.admin.socialAsrConfig)
  return response.data
}

export async function updateAsrConfig(
  data: ApiAsrConfigUpdateRequest,
): Promise<ApiAsrConfig> {
  const response = await apiClient.put<ApiAsrConfig>(
    ENDPOINTS.admin.socialAsrConfig,
    data,
  )
  return response.data
}

export async function testAsrConfig(): Promise<ApiAsrConfigTestResult> {
  const response = await apiClient.post<ApiAsrConfigTestResult>(
    ENDPOINTS.admin.socialAsrConfigTest,
  )
  return response.data
}
