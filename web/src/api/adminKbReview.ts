import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiKbBatchApproveResult,
  ApiKbChaptersPublishRequest,
  ApiKbChaptersResponse,
  ApiKbImageAsset,
  ApiKbImageExcludedRequest,
  ApiKbImageListResponse,
  ApiKbKnowledgePoint,
  ApiKbPointCreateRequest,
  ApiKbPointListResponse,
  ApiKbPointPatchRequest,
  ApiKbPointRejectRequest,
  ApiKbPointsBatchApproveRequest,
  ApiKbPointsMergeRequest,
  ApiKbUsageResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

// ---- 建库用量 ----

export async function fetchKbUsage(
  params: {
    sourceId?: number
    dateFrom?: string
    dateTo?: string
  } = {}
): Promise<ApiKbUsageResponse> {
  // query 参数跟随后端签名 snake_case（source_id/date_from/date_to）
  const response = await apiClient.get<ApiKbUsageResponse>(ENDPOINTS.admin.kbUsage, {
    params: {
      source_id: params.sourceId,
      date_from: params.dateFrom,
      date_to: params.dateTo,
    },
  })
  return response.data
}

// ---- 章节发布 ----

export async function fetchKbChapters(
  sourceId: number
): Promise<ApiKbChaptersResponse> {
  const response = await apiClient.get<ApiKbChaptersResponse>(
    ENDPOINTS.admin.kbSourceChapters(sourceId)
  )
  return response.data
}

export async function publishKbChapters(
  sourceId: number,
  data: ApiKbChaptersPublishRequest
): Promise<ApiKbChaptersResponse> {
  const response = await apiClient.post<ApiKbChaptersResponse>(
    ENDPOINTS.admin.kbSourceChaptersPublish(sourceId),
    data
  )
  return response.data
}

// ---- 知识审核（F-KB-03）----

export async function fetchKbReviewPoints(
  sourceId: number,
  params: { status?: string; page?: number; pageSize?: number } = {}
): Promise<ApiKbPointListResponse> {
  // query 参数跟随后端签名 snake_case（page_size），camel 键会被 FastAPI 静默忽略
  const response = await apiClient.get<ApiKbPointListResponse>(
    ENDPOINTS.admin.kbSourcePoints(sourceId),
    {
      params: {
        status: params.status,
        page: params.page,
        page_size: params.pageSize,
      },
    }
  )
  return response.data
}

export async function fetchKbImages(
  sourceId: number,
  params: {
    mediaId?: number
    status?: string
    page?: number
    pageSize?: number
  } = {}
): Promise<ApiKbImageListResponse> {
  const response = await apiClient.get<ApiKbImageListResponse>(
    ENDPOINTS.admin.kbSourceImages(sourceId),
    {
      params: {
        media_id: params.mediaId,
        status: params.status,
        page: params.page,
        page_size: params.pageSize,
      },
    }
  )
  return response.data
}

export async function redescribeKbImage(imageId: number): Promise<ApiKbImageAsset> {
  const response = await apiClient.post<ApiKbImageAsset>(
    ENDPOINTS.admin.kbImageRedescribe(imageId)
  )
  return response.data
}

export async function patchKbImage(
  imageId: number,
  data: ApiKbImageExcludedRequest
): Promise<ApiKbImageAsset> {
  const response = await apiClient.patch<ApiKbImageAsset>(
    ENDPOINTS.admin.kbImage(imageId),
    data
  )
  return response.data
}

export async function createKbPoint(
  data: ApiKbPointCreateRequest
): Promise<ApiKbKnowledgePoint> {
  const response = await apiClient.post<ApiKbKnowledgePoint>(
    ENDPOINTS.admin.kbPoints,
    data
  )
  return response.data
}

export async function patchKbPoint(
  pointId: number,
  data: ApiKbPointPatchRequest
): Promise<ApiKbKnowledgePoint> {
  const response = await apiClient.patch<ApiKbKnowledgePoint>(
    ENDPOINTS.admin.kbPoint(pointId),
    data
  )
  return response.data
}

export async function approveKbPoint(pointId: number): Promise<ApiKbKnowledgePoint> {
  const response = await apiClient.post<ApiKbKnowledgePoint>(
    ENDPOINTS.admin.kbPointApprove(pointId)
  )
  return response.data
}

export async function rejectKbPoint(
  pointId: number,
  data: ApiKbPointRejectRequest
): Promise<ApiKbKnowledgePoint> {
  const response = await apiClient.post<ApiKbKnowledgePoint>(
    ENDPOINTS.admin.kbPointReject(pointId),
    data
  )
  return response.data
}

export async function mergeKbPoints(
  data: ApiKbPointsMergeRequest
): Promise<ApiKbKnowledgePoint> {
  const response = await apiClient.post<ApiKbKnowledgePoint>(
    ENDPOINTS.admin.kbPointsMerge,
    data
  )
  return response.data
}

export async function approveKbPointsBatch(
  data: ApiKbPointsBatchApproveRequest
): Promise<ApiKbBatchApproveResult> {
  const response = await apiClient.post<ApiKbBatchApproveResult>(
    ENDPOINTS.admin.kbPointsApproveBatch,
    data
  )
  return response.data
}
