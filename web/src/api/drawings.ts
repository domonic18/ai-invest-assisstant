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

/** AI 画线单条原位编辑：拖拽锚点 / 双击改名（F-DRAW-08） */
export async function updateAiDrawingItem(payload: {
  targetType: KlineDrawingTargetType
  targetCode: string
  period: 'daily' | 'weekly' | 'monthly'
  label: string
  anchors?: UserKlineDrawing['anchors']
  newLabel?: string
}) {
  const response = await apiClient.patch<{ label: string }>(
    ENDPOINTS.klineDrawings.aiItem,
    payload,
  )
  return response.data
}

/** AI 画线单条删除（Delete 键） */
export async function deleteAiDrawingItem(payload: {
  targetType: KlineDrawingTargetType
  targetCode: string
  period: 'daily' | 'weekly' | 'monthly'
  label: string
}) {
  const params = {
    target_type: payload.targetType,
    target_code: payload.targetCode,
    period: payload.period,
    label: payload.label,
  }
  await apiClient.delete(ENDPOINTS.klineDrawings.aiItem, { params })
}

/** 清空指定标的+周期的 AI 画线集（对话重新生成即恢复） */
export async function clearAiDrawings(payload: {
  targetType: KlineDrawingTargetType
  targetCode: string
  period: 'daily' | 'weekly' | 'monthly'
}) {
  const params = {
    target_type: payload.targetType,
    target_code: payload.targetCode,
    period: payload.period,
  }
  await apiClient.delete(ENDPOINTS.klineDrawings.aiClear, { params })
}
