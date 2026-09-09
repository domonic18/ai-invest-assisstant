import { ENDPOINTS } from '@ai-invest/shared'
import type {
  AdminAiResultListParams,
  AdminAiResultDetail,
  AdminAiSkillInfo,
  ApiAdminAiResultDetail,
  ApiAdminAiResultItem,
  ApiAdminAiSkillInfo,
  ApiPaginatedResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapAdminAiResult, mapAdminAiResultDetail, mapAdminAiSkill, mapPaginatedResponse } from './mappers'

export async function fetchAiResultSkills(): Promise<AdminAiSkillInfo[]> {
  const response = await apiClient.get<ApiAdminAiSkillInfo[]>(
    ENDPOINTS.admin.aiResultSkills,
  )
  return response.data.map(mapAdminAiSkill)
}

export async function fetchAdminAiResults(params: AdminAiResultListParams) {
  const response = await apiClient.get<
    ApiPaginatedResponse<ApiAdminAiResultItem>
  >(ENDPOINTS.admin.aiResults, {
    params: {
      skill_id: params.skillId,
      status: params.status,
      start_date: params.startDate,
      end_date: params.endDate,
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
    },
  })
  return mapPaginatedResponse(response.data, mapAdminAiResult)
}

export async function fetchAdminAiResultDetail(id: number): Promise<AdminAiResultDetail> {
  const response = await apiClient.get<ApiAdminAiResultDetail>(
    ENDPOINTS.admin.aiResult(id),
  )
  return mapAdminAiResultDetail(response.data)
}

export async function deleteAdminAiResult(id: number) {
  await apiClient.delete(ENDPOINTS.admin.aiResult(id))
}
