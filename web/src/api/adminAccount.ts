import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAccountSettings,
  ApiAccountSettingsUpdateRequest,
  ApiApproveRequest,
  ApiPendingApplication,
  ApiQuotaAdjustRequest,
  ApiRejectRequest,
  ApiUsageDashboardResponse,
  ApiUsagePerUser,
  PendingApplication,
} from '@ai-invest/shared'

import { apiClient } from './client'

export function mapPendingApplication(dto: ApiPendingApplication): PendingApplication {
  return dto
}

export async function fetchPendingApplications(): Promise<PendingApplication[]> {
  const response = await apiClient.get<ApiPendingApplication[]>(
    ENDPOINTS.admin.usersPending,
  )
  return response.data.map(mapPendingApplication)
}

export async function fetchPendingCount(): Promise<number> {
  const response = await apiClient.get<number>(ENDPOINTS.admin.usersPendingCount)
  return response.data
}

export async function approveUser(id: number, data: ApiApproveRequest = {}) {
  await apiClient.post(ENDPOINTS.admin.userApprove(id), data)
}

export async function rejectUser(id: number, data: ApiRejectRequest) {
  await apiClient.post(ENDPOINTS.admin.userReject(id), data)
}

export async function adjustUserQuota(id: number, data: ApiQuotaAdjustRequest) {
  await apiClient.post(ENDPOINTS.admin.userQuota(id), data)
}

export async function fetchUsageDashboard(days = 30): Promise<ApiUsageDashboardResponse> {
  const response = await apiClient.get<ApiUsageDashboardResponse>(
    ENDPOINTS.admin.usageDashboard(days),
  )
  return response.data
}

export async function fetchUsagePerUsers(days = 30): Promise<ApiUsagePerUser[]> {
  const response = await apiClient.get<ApiUsagePerUser[]>(
    ENDPOINTS.admin.usagePerUsers(days),
  )
  return response.data
}

export async function fetchAccountSettings(): Promise<ApiAccountSettings> {
  const response = await apiClient.get<ApiAccountSettings>(
    ENDPOINTS.admin.accountSettings,
  )
  return response.data
}

export async function updateAccountSettings(data: ApiAccountSettingsUpdateRequest) {
  const response = await apiClient.put<ApiAccountSettings>(
    ENDPOINTS.admin.accountSettings,
    data,
  )
  return response.data
}
