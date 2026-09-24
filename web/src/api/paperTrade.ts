/** 模拟盘 API（总览实时透传 + 本地委托/成交/净值只读查询）。 */

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiPaperTradeExecutionPage,
  ApiPaperTradeNavResponse,
  ApiPaperTradeOrderPage,
  ApiPaperTradeOverview,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchPaperTradeOverview(): Promise<ApiPaperTradeOverview> {
  const response = await apiClient.get<ApiPaperTradeOverview>(
    ENDPOINTS.paperTrade.overview,
  )
  return response.data
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value))
  }
  const qs = query.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchPaperTradeOrders(
  params: { tradeDate?: string; page?: number; pageSize?: number } = {},
): Promise<ApiPaperTradeOrderPage> {
  const url =
    ENDPOINTS.paperTrade.orders +
    toQuery({
      trade_date: params.tradeDate,
      page: params.page,
      page_size: params.pageSize,
    })
  const response = await apiClient.get<ApiPaperTradeOrderPage>(url)
  return response.data
}

export async function fetchPaperTradeExecutions(
  params: { tradeDate?: string; page?: number; pageSize?: number } = {},
): Promise<ApiPaperTradeExecutionPage> {
  const url =
    ENDPOINTS.paperTrade.executions +
    toQuery({
      trade_date: params.tradeDate,
      page: params.page,
      page_size: params.pageSize,
    })
  const response = await apiClient.get<ApiPaperTradeExecutionPage>(url)
  return response.data
}

export async function fetchPaperTradeNav(days = 30): Promise<ApiPaperTradeNavResponse> {
  const response = await apiClient.get<ApiPaperTradeNavResponse>(
    `${ENDPOINTS.paperTrade.nav}?days=${days}`,
  )
  return response.data
}
