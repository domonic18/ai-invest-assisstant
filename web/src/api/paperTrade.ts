/** 模拟交易 API（账户配置 + 总览实时透传 + 本地委托/成交/净值查询 + 人工交易）。 */

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiPaperTradeAccount,
  ApiPaperTradeAccountList,
  ApiPaperTradeAccountSaveRequest,
  ApiPaperTradeAccountSyncResponse,
  ApiPaperTradeActionResponse,
  ApiPaperTradeAdminAccount,
  ApiPaperTradeAdminAccountList,
  ApiPaperTradeExecutionPage,
  ApiPaperTradeNavResponse,
  ApiPaperTradeOrderPage,
  ApiPaperTradeOverview,
  ApiPaperTradePlaceOrderRequest,
  ApiPaperTradeTradeMarkerResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

function toQuery(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value))
  }
  const qs = query.toString()
  return qs ? `?${qs}` : ''
}

// ============================================================
// 账户配置
// ============================================================

export async function fetchPaperTradeAccounts(): Promise<ApiPaperTradeAccountList> {
  const response = await apiClient.get<ApiPaperTradeAccountList>(
    ENDPOINTS.paperTrade.accounts,
  )
  return response.data
}

export async function createPaperTradeAccount(
  data: ApiPaperTradeAccountSaveRequest,
): Promise<ApiPaperTradeAccount> {
  const response = await apiClient.post<ApiPaperTradeAccount>(
    ENDPOINTS.paperTrade.accounts,
    data,
  )
  return response.data
}

export async function updatePaperTradeAccount(
  accountId: number,
  data: Partial<ApiPaperTradeAccountSaveRequest>,
): Promise<ApiPaperTradeAccount> {
  const response = await apiClient.put<ApiPaperTradeAccount>(
    ENDPOINTS.paperTrade.account(accountId),
    data,
  )
  return response.data
}

export async function deletePaperTradeAccount(accountId: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.paperTrade.account(accountId))
}

// ============================================================
// 管理端（列表 / 指定 agent / 启停）
// ============================================================

export async function fetchAdminPaperTradeAccounts(): Promise<ApiPaperTradeAdminAccountList> {
  const response = await apiClient.get<ApiPaperTradeAdminAccountList>(
    ENDPOINTS.admin.paperTradeAccounts,
  )
  return response.data
}

export async function designatePaperTradeAgentAccount(
  accountId: number,
): Promise<ApiPaperTradeAdminAccount> {
  const response = await apiClient.put<ApiPaperTradeAdminAccount>(
    ENDPOINTS.admin.paperTradeAccountAgent(accountId),
  )
  return response.data
}

export async function setPaperTradeAccountEnabled(
  accountId: number,
  enabled: boolean,
): Promise<ApiPaperTradeAdminAccount> {
  const response = await apiClient.put<ApiPaperTradeAdminAccount>(
    ENDPOINTS.admin.paperTradeAccountEnabled(accountId),
    { enabled },
  )
  return response.data
}

// ============================================================
// 行情与交易查询（恒按账户）
// ============================================================

export async function fetchPaperTradeOverview(
  accountId: number,
): Promise<ApiPaperTradeOverview> {
  const response = await apiClient.get<ApiPaperTradeOverview>(
    ENDPOINTS.paperTrade.overview + toQuery({ account_id: accountId }),
  )
  return response.data
}

export async function fetchPaperTradeOrders(
  params: {
    accountId: number
    tradeDate?: string
    page?: number
    pageSize?: number
  },
): Promise<ApiPaperTradeOrderPage> {
  const url =
    ENDPOINTS.paperTrade.orders +
    toQuery({
      account_id: params.accountId,
      trade_date: params.tradeDate,
      page: params.page,
      page_size: params.pageSize,
    })
  const response = await apiClient.get<ApiPaperTradeOrderPage>(url)
  return response.data
}

export async function fetchPaperTradeExecutions(
  params: {
    accountId: number
    tradeDate?: string
    page?: number
    pageSize?: number
  },
): Promise<ApiPaperTradeExecutionPage> {
  const url =
    ENDPOINTS.paperTrade.executions +
    toQuery({
      account_id: params.accountId,
      trade_date: params.tradeDate,
      page: params.page,
      page_size: params.pageSize,
    })
  const response = await apiClient.get<ApiPaperTradeExecutionPage>(url)
  return response.data
}

export async function fetchPaperTradeNav(
  accountId: number,
  days = 30,
): Promise<ApiPaperTradeNavResponse> {
  const response = await apiClient.get<ApiPaperTradeNavResponse>(
    ENDPOINTS.paperTrade.nav +
      toQuery({ account_id: accountId, days }),
  )
  return response.data
}

/** 当前用户对指定标的的成交回报（个股图表 B/S/T 标记）。 */
export async function fetchPaperTradeTradeMarkers(
  stockCode: string,
  days = 120,
): Promise<ApiPaperTradeTradeMarkerResponse> {
  const response = await apiClient.get<ApiPaperTradeTradeMarkerResponse>(
    ENDPOINTS.paperTrade.tradeMarkers +
      toQuery({ stock_code: stockCode, days }),
  )
  return response.data
}

// ============================================================
// 人工交易（agent 专属账户 403）
// ============================================================

export async function placePaperTradeOrder(
  data: ApiPaperTradePlaceOrderRequest,
): Promise<ApiPaperTradeActionResponse> {
  const response = await apiClient.post<ApiPaperTradeActionResponse>(
    ENDPOINTS.paperTrade.orders,
    data,
  )
  return response.data
}

export async function cancelPaperTradeOrder(
  accountId: number,
  clOrdId: string,
): Promise<ApiPaperTradeActionResponse> {
  const response = await apiClient.delete<ApiPaperTradeActionResponse>(
    ENDPOINTS.paperTrade.order(clOrdId) + toQuery({ account_id: accountId }),
  )
  return response.data
}

/** 单账户即时同步：下单/撤单后让本地委托成交历史立即反映柜台状态。 */
export async function syncPaperTradeAccount(
  accountId: number,
): Promise<ApiPaperTradeAccountSyncResponse> {
  const response = await apiClient.post<ApiPaperTradeAccountSyncResponse>(
    ENDPOINTS.paperTrade.accountSync(accountId),
  )
  return response.data
}
