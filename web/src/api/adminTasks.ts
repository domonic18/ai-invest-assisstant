import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAdminTaskCreateRequest,
  ApiAdminTaskResponse,
  ApiAdminTaskUpdateRequest,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminTask, mapPaginatedResponse } from './mappers'

export interface AdminTaskParams {
  page?: number
  pageSize?: number
}

export async function fetchAdminTasks(params: AdminTaskParams = {}) {
  const response = await apiClient.get<ApiPaginatedResponse<ApiAdminTaskResponse>>(
    ENDPOINTS.admin.tasks,
    {
      params: {
        page: params.page ?? 1,
        page_size: params.pageSize ?? 20,
      },
    },
  )
  return mapPaginatedResponse(response.data, mapAdminTask)
}

export async function createAdminTask(data: ApiAdminTaskCreateRequest) {
  const response = await apiClient.post<ApiAdminTaskResponse>(
    ENDPOINTS.admin.tasks,
    data,
  )
  return mapAdminTask(response.data)
}

export async function updateAdminTask(
  id: number,
  data: ApiAdminTaskUpdateRequest,
) {
  const response = await apiClient.put<ApiAdminTaskResponse>(
    ENDPOINTS.admin.task(id),
    data,
  )
  return mapAdminTask(response.data)
}

export async function deleteAdminTask(id: number) {
  await apiClient.delete(ENDPOINTS.admin.task(id))
}

export async function pauseAdminTask(id: number) {
  const response = await apiClient.post<ApiAdminTaskResponse>(
    ENDPOINTS.admin.taskPause(id),
  )
  return mapAdminTask(response.data)
}

export async function resumeAdminTask(id: number) {
  const response = await apiClient.post<ApiAdminTaskResponse>(
    ENDPOINTS.admin.taskResume(id),
  )
  return mapAdminTask(response.data)
}

export async function triggerAdminTask(id: number) {
  const response = await apiClient.post<ApiAdminTaskResponse>(
    ENDPOINTS.admin.taskTrigger(id),
  )
  return mapAdminTask(response.data)
}
