import { ENDPOINTS } from '@ai-invest/shared'

import type { StockScreeningRow } from '@/stores/assistant'

import { apiClient } from './client'

/** 问财直查响应（stocks 行 = stockCode/stockName 固定列 + 问财原始中文列透传） */
export interface ScreeningQueryResponse {
  query: string
  total: number
  truncated: boolean
  columns: string[]
  stocks: StockScreeningRow[]
}

/** 问财即席选股直查；超时放宽以覆盖网关放宽改写重试链（默认 30s 不够） */
export async function queryScreening(query: string, limit = 100): Promise<ScreeningQueryResponse> {
  const response = await apiClient.post<ScreeningQueryResponse>(
    ENDPOINTS.screening.query,
    { query, limit },
    { timeout: 60000 },
  )
  return response.data
}
