import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiUserGroupCreateRequest,
  ApiUserGroupResponse,
  ApiUserGroupUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchAdminUserGroups() {
  const response = await apiClient.get<ApiUserGroupResponse[]>(ENDPOINTS.admin.userGroups)
  return response.data
}

export async function createAdminUserGroup(data: ApiUserGroupCreateRequest) {
  const response = await apiClient.post<ApiUserGroupResponse>(ENDPOINTS.admin.userGroups, data)
  return response.data
}

export async function updateAdminUserGroup(
  id: number,
  data: ApiUserGroupUpdateRequest,
) {
  const response = await apiClient.put<ApiUserGroupResponse>(
    ENDPOINTS.admin.userGroup(id),
    data,
  )
  return response.data
}

export async function deleteAdminUserGroup(id: number) {
  await apiClient.delete(ENDPOINTS.admin.userGroup(id))
}
