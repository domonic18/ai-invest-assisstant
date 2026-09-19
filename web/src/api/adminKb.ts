import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiKbConfirmCostRequest,
  ApiKbConfirmCostResponse,
  ApiKbCostEstimateRequest,
  ApiKbCostEstimateResponse,
  ApiKbMediaInitRequest,
  ApiKbMediaInitResponse,
  ApiKbMediaPatchRequest,
  ApiKbMediaResponse,
  ApiKbSettingsResponse,
  ApiKbSettingsUpdateRequest,
  ApiKbSourceCreateRequest,
  ApiKbSourceResponse,
  ApiKbSourceUpdateRequest,
  ApiKbTranscriptResponse,
  ApiKbTranscriptSaveResponse,
  ApiKbTranscriptUpdateRequest,
} from '@ai-invest/shared'
import axios from 'axios'

import { apiClient } from './client'

// ---- 知识库设置 ----

export async function fetchKbSettings(): Promise<ApiKbSettingsResponse> {
  const response = await apiClient.get<ApiKbSettingsResponse>(ENDPOINTS.admin.kbSettings)
  return response.data
}

export async function updateKbSettings(
  data: ApiKbSettingsUpdateRequest
): Promise<ApiKbSettingsResponse> {
  const response = await apiClient.put<ApiKbSettingsResponse>(
    ENDPOINTS.admin.kbSettings,
    data
  )
  return response.data
}

// ---- 知识源 ----

export async function fetchKbSources(): Promise<ApiKbSourceResponse[]> {
  const response = await apiClient.get<ApiKbSourceResponse[]>(ENDPOINTS.admin.kbSources)
  return response.data
}

export async function createKbSource(
  data: ApiKbSourceCreateRequest
): Promise<ApiKbSourceResponse> {
  const response = await apiClient.post<ApiKbSourceResponse>(ENDPOINTS.admin.kbSources, data)
  return response.data
}

export async function updateKbSource(
  id: number,
  data: ApiKbSourceUpdateRequest
): Promise<ApiKbSourceResponse> {
  const response = await apiClient.patch<ApiKbSourceResponse>(
    ENDPOINTS.admin.kbSource(id),
    data
  )
  return response.data
}

export async function deleteKbSource(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.kbSource(id))
}

export async function restoreKbSource(id: number): Promise<ApiKbSourceResponse> {
  const response = await apiClient.post<ApiKbSourceResponse>(
    ENDPOINTS.admin.kbSourceRestore(id)
  )
  return response.data
}

// ---- 素材 ----

export async function fetchKbSourceMedia(
  sourceId: number
): Promise<ApiKbMediaResponse[]> {
  const response = await apiClient.get<ApiKbMediaResponse[]>(
    ENDPOINTS.admin.kbSourceMedia(sourceId)
  )
  return response.data
}

export async function initKbMediaUploads(
  sourceId: number,
  data: ApiKbMediaInitRequest
): Promise<ApiKbMediaInitResponse> {
  const response = await apiClient.post<ApiKbMediaInitResponse>(
    ENDPOINTS.admin.kbSourceMediaInit(sourceId),
    data
  )
  return response.data
}

export async function confirmKbMediaUploaded(
  mediaId: number
): Promise<ApiKbMediaResponse> {
  const response = await apiClient.post<ApiKbMediaResponse>(
    ENDPOINTS.admin.kbMediaUploaded(mediaId)
  )
  return response.data
}

export async function patchKbMedia(
  mediaId: number,
  data: ApiKbMediaPatchRequest
): Promise<ApiKbMediaResponse> {
  const response = await apiClient.patch<ApiKbMediaResponse>(
    ENDPOINTS.admin.kbMedia(mediaId),
    data
  )
  return response.data
}

export async function deleteKbMedia(mediaId: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.kbMedia(mediaId))
}

// ---- 费用闸门 ----

export async function estimateKbCost(
  data: ApiKbCostEstimateRequest
): Promise<ApiKbCostEstimateResponse> {
  const response = await apiClient.post<ApiKbCostEstimateResponse>(
    ENDPOINTS.admin.kbCostEstimate,
    data
  )
  return response.data
}

export async function confirmKbCost(
  sourceId: number,
  data: ApiKbConfirmCostRequest
): Promise<ApiKbConfirmCostResponse> {
  const response = await apiClient.post<ApiKbConfirmCostResponse>(
    ENDPOINTS.admin.kbSourceConfirmCost(sourceId),
    data
  )
  return response.data
}

// ---- 文稿编辑 ----

export async function fetchKbTranscript(
  sourceId: number,
  mediaId: number
): Promise<ApiKbTranscriptResponse> {
  const response = await apiClient.get<ApiKbTranscriptResponse>(
    ENDPOINTS.admin.kbSourceTranscript(sourceId, mediaId)
  )
  return response.data
}

export async function saveKbTranscript(
  sourceId: number,
  mediaId: number,
  data: ApiKbTranscriptUpdateRequest
): Promise<ApiKbTranscriptSaveResponse> {
  const response = await apiClient.put<ApiKbTranscriptSaveResponse>(
    ENDPOINTS.admin.kbSourceTranscript(sourceId, mediaId),
    data
  )
  return response.data
}

/**
 * 浏览器直传 COS（预签名 PUT，独立 axios 实例：
 * 不带业务 baseURL/鉴权头，避免干扰预签名校验）。
 */
export async function putFileToCos(
  uploadUrl: string,
  file: File,
  onProgress?: (pct: number) => void
): Promise<void> {
  await axios.put(uploadUrl, file, {
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    onUploadProgress: (e) => {
      if (e.total) onProgress?.(Math.round((e.loaded / e.total) * 100))
    },
  })
}
