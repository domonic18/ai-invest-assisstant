/**
 * K 线画线 API（F-DRAW）：用户画线 CRUD + AI 画线采纳。
 * wire 契约 = shared/types/drawing.ts（camelCase 单一真相源）。
 */

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  AiKlineDrawingGroup,
  KlineDrawingTargetType,
  UserKlineDrawing,
  UserKlineDrawingCreateRequest,
  UserKlineDrawingUpdateRequest,
} from '@ai-invest/shared'

import { apiClient } from './client'

export interface KlineDrawingsResult {
  user: UserKlineDrawing[]
  ai: AiKlineDrawingGroup[]
}

export async function fetchKlineDrawings(targetType: KlineDrawingTargetType, targetCode: string) {
  const response = await apiClient.get<KlineDrawingsResult>(ENDPOINTS.klineDrawings.base, {
    params: { target_type: targetType, target_code: targetCode },
  })
  return response.data
}

export async function createKlineDrawing(payload: UserKlineDrawingCreateRequest) {
  const response = await apiClient.post<UserKlineDrawing>(ENDPOINTS.klineDrawings.base, payload)
  return response.data
}

export async function updateKlineDrawing(id: string, data: UserKlineDrawingUpdateRequest) {
  const response = await apiClient.patch<UserKlineDrawing>(ENDPOINTS.klineDrawings.item(id), data)
  return response.data
}

export async function deleteKlineDrawing(id: string) {
  await apiClient.delete(ENDPOINTS.klineDrawings.item(id))
}

/** AI 画线单条采纳：复制为用户画线（原 AI 画线保留） */
export async function adoptAiDrawing(payload: {
  targetType: KlineDrawingTargetType
  targetCode: string
  period: 'daily' | 'weekly' | 'monthly'
  label: string
  style: UserKlineDrawingCreateRequest['style']
}) {
  const response = await apiClient.post<UserKlineDrawing>(ENDPOINTS.klineDrawings.adopt, payload)
  return response.data
}
