import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiCustomSkillCreateRequest,
  ApiCustomSkillUpdateRequest,
  ApiSkillFilesResponse,
  ApiSkillResponse,
  ApiSkillSquareResponse,
  ApiUserSkillResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchSkillSquare(): Promise<ApiSkillSquareResponse> {
  const response = await apiClient.get<ApiSkillSquareResponse>(ENDPOINTS.skills.list)
  return response.data
}

export async function fetchSkillDetail(skillId: string): Promise<ApiSkillResponse> {
  const response = await apiClient.get<ApiSkillResponse>(ENDPOINTS.skills.detail(skillId))
  return response.data
}

export async function fetchSkillFiles(skillId: string): Promise<ApiSkillFilesResponse> {
  const response = await apiClient.get<ApiSkillFilesResponse>(ENDPOINTS.skills.files(skillId))
  return response.data
}

export async function installSkill(skillId: string): Promise<ApiUserSkillResponse> {
  const response = await apiClient.post<ApiUserSkillResponse>(
    ENDPOINTS.skills.install(skillId),
  )
  return response.data
}

export async function uninstallSkill(skillId: string): Promise<void> {
  await apiClient.delete(ENDPOINTS.skills.uninstall(skillId))
}

export async function createCustomSkill(
  payload: ApiCustomSkillCreateRequest,
): Promise<ApiSkillResponse> {
  const response = await apiClient.post<ApiSkillResponse>(ENDPOINTS.skills.create, payload)
  return response.data
}

export async function updateCustomSkill(
  skillId: string,
  payload: ApiCustomSkillUpdateRequest,
): Promise<ApiSkillResponse> {
  const response = await apiClient.patch<ApiSkillResponse>(
    ENDPOINTS.skills.update(skillId),
    payload,
  )
  return response.data
}

export async function publishCustomSkill(skillId: string): Promise<ApiSkillResponse> {
  const response = await apiClient.post<ApiSkillResponse>(ENDPOINTS.skills.publish(skillId))
  return response.data
}
