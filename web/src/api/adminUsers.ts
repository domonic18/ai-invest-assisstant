import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAdminUserCreateRequest,
  ApiAdminUserResetPasswordRequest,
  ApiAdminUserResponse,
  ApiAdminUserUpdateRequest,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminUser, mapPaginatedResponse } from './mappers'

export interface AdminUserParams {
  page?: number
  pageSize?: number
}

export async function fetchAdminUsers(params: AdminUserParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiAdminUserResponse>>(
    ENDPOINTS.admin.users,
    {
      params: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    },
  )
  return mapPaginatedResponse(response.data, mapAdminUser)
}

export async function createAdminUser(data: ApiAdminUserCreateRequest) {
  const response = await apiClient.post<ApiAdminUserResponse>(
    ENDPOINTS.admin.users,
    data,
  )
  return mapAdminUser(response.data)
}

export async function updateAdminUser(
  id: number,
  data: ApiAdminUserUpdateRequest,
) {
  const response = await apiClient.put<ApiAdminUserResponse>(
    ENDPOINTS.admin.user(id),
    data,
  )
  return mapAdminUser(response.data)
}

export async function deleteAdminUser(id: number) {
  await apiClient.delete(ENDPOINTS.admin.user(id))
}

export async function resetAdminUserPassword(
  id: number,
  data: ApiAdminUserResetPasswordRequest,
) {
  const response = await apiClient.post<ApiAdminUserResponse>(
    ENDPOINTS.admin.userResetPassword(id),
    data,
  )
  return mapAdminUser(response.data)
}
