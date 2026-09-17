/** 社媒大 V 情绪 API（用户侧情绪流/账号卡/时间线）。 */

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiSocialAccountsResponse,
  ApiSocialFeedPage,
  ApiSocialStance,
  ApiSocialTimelinePage,
} from '@ai-invest/shared'

import { apiClient } from './client'

export interface SentimentFeedParams {
  /** 账号分类过滤（macro_policy/finance_kol/industry） */
  category?: string
  stance?: ApiSocialStance
  /** 只看近 N 小时（后端上限 168） */
  hours?: number
  /** 仅强信号（置信度 ≥ 0.8） */
  strongOnly?: boolean
  page?: number
  pageSize?: number
}

function toQuery(params: Record<string, string | number | boolean | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value))
  }
  const qs = query.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchSentimentFeed(
  params: SentimentFeedParams = {},
): Promise<ApiSocialFeedPage> {
  const url =
    ENDPOINTS.social.sentimentFeed +
    toQuery({
      category: params.category,
      stance: params.stance,
      hours: params.hours,
      strong_only: params.strongOnly,
      page: params.page,
      page_size: params.pageSize,
    })
  const response = await apiClient.get<ApiSocialFeedPage>(url)
  return response.data
}

/** 账号维度卡；hours 为统计窗口（小时），缺省=全部历史。 */
export async function fetchSocialAccountCards(
  hours?: number,
): Promise<ApiSocialAccountsResponse> {
  const url = ENDPOINTS.social.accounts + toQuery({ hours })
  const response = await apiClient.get<ApiSocialAccountsResponse>(url)
  return response.data
}

export async function fetchSocialTimeline(
  accountId: number,
  params: { page?: number; pageSize?: number } = {},
): Promise<ApiSocialTimelinePage> {
  const url =
    ENDPOINTS.social.accountTimeline(accountId) +
    toQuery({ page: params.page, page_size: params.pageSize })
  const response = await apiClient.get<ApiSocialTimelinePage>(url)
  return response.data
}
