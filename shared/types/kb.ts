/**
 * 知识库域（F-KB）wire 类型：与 backend/app/schemas/kb.py CamelModel 单一真相源对齐。
 */

/** 知识库设置响应（管理后台读写共用）。 */
export interface ApiKbSettingsResponse {
  hotwords: string[]
  segmentMaxSeconds: number
  asrConcurrency: number
  topK: number
  unitPrices: Record<string, number>
  embeddingConfigId: number | null
  cleanModelId: number | null
  extractModelId: number | null
  visionModelId: number | null
  authorizedUserIds: number[]
  updatedAt: string | null
}

/** 知识库设置保存请求（全部可选，仅提交的字段更新）。 */
export interface ApiKbSettingsUpdateRequest {
  hotwords?: string[]
  segmentMaxSeconds?: number
  asrConcurrency?: number
  topK?: number
  unitPrices?: Record<string, number>
  embeddingConfigId?: number | null
  cleanModelId?: number | null
  extractModelId?: number | null
  visionModelId?: number | null
  authorizedUserIds?: number[]
}
