import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiTelegraphPage } from '@ai-invest/shared'

import { apiClient } from './client'

export interface TelegraphListParams {
  page?: number
  pageSize?: number
  category?: string
  minImportance?: number
  minAiScore?: number
  /** 仅看订阅命中条目（登录用户维度）。 */
  subscriptionOnly?: boolean
}

export async function fetchTelegraph(
  params: TelegraphListParams = {},
): Promise<ApiTelegraphPage> {
  const query = new URLSearchParams()
  if (params.page !== undefined) query.set('page', String(params.page))
  if (params.pageSize !== undefined) query.set('page_size', String(params.pageSize))
  if (params.category) query.set('category', params.category)
  if (params.minImportance !== undefined)
    query.set('min_importance', String(params.minImportance))
  if (params.minAiScore !== undefined)
    query.set('min_ai_score', String(params.minAiScore))
  if (params.subscriptionOnly) query.set('subscription_only', 'true')
  const qs = query.toString()
  const url = qs ? `${ENDPOINTS.telegraph.list}?${qs}` : ENDPOINTS.telegraph.list
  const response = await apiClient.get<ApiTelegraphPage>(url)
  return response.data
}
