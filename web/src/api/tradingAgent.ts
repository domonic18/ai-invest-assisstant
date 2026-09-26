/** 交易 Agent API（admin /admin/trading-agent/*，批次 5 配置 + 批次 6 复盘 + 批次 7 计划）。 */

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiAgentWatchlistGroupResponse,
  ApiTradingAgentConfig,
  ApiTradingAgentConfigUpdateRequest,
  ApiTradingAgentDates,
  ApiTradingAgentPlan,
  ApiTradingAgentReview,
  TradingReviewPeriod,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchTradingAgentConfig(): Promise<ApiTradingAgentConfig> {
  const response = await apiClient.get<ApiTradingAgentConfig>(
    ENDPOINTS.admin.tradingAgentConfig,
  )
  return response.data
}

export async function updateTradingAgentConfig(
  data: ApiTradingAgentConfigUpdateRequest,
): Promise<ApiTradingAgentConfig> {
  const response = await apiClient.put<ApiTradingAgentConfig>(
    ENDPOINTS.admin.tradingAgentConfig,
    data,
  )
  return response.data
}

export async function fetchTradingAgentReview(
  period: TradingReviewPeriod,
  tradeDate?: string,
): Promise<ApiTradingAgentReview> {
  const response = await apiClient.get<ApiTradingAgentReview>(
    ENDPOINTS.admin.tradingAgentReview,
    { params: tradeDate ? { period, trade_date: tradeDate } : { period } },
  )
  return response.data
}

/** 有记录日期清单（日历打点：计划日 + 各周期已生成复盘的基准日）。 */
export async function fetchTradingAgentDates(): Promise<ApiTradingAgentDates> {
  const response = await apiClient.get<ApiTradingAgentDates>(
    ENDPOINTS.admin.tradingAgentDates,
  )
  return response.data
}

/** 指定日交易计划（缺省 trade_date 时后端取最近交易日；含全部状态）。 */
export async function fetchTradingAgentPlans(tradeDate?: string): Promise<ApiTradingAgentPlan[]> {
  const response = await apiClient.get<ApiTradingAgentPlan[]>(
    ENDPOINTS.admin.tradingAgentPlans,
    { params: tradeDate ? { trade_date: tradeDate } : undefined },
  )
  return response.data
}

/** 人工取消当日 active 计划（triggered 后不可取消）。 */
export async function cancelTradingAgentPlan(planId: number): Promise<ApiTradingAgentPlan> {
  const response = await apiClient.post<ApiTradingAgentPlan>(
    ENDPOINTS.admin.tradingAgentPlanCancel(planId),
  )
  return response.data
}

/** agent 自选分组（null = 尚未生成选股）。 */
export async function fetchTradingAgentSelections(): Promise<ApiAgentWatchlistGroupResponse | null> {
  const response = await apiClient.get<ApiAgentWatchlistGroupResponse | null>(
    ENDPOINTS.admin.tradingAgentSelections,
  )
  return response.data
}

/** 人工移出 agent 选股（全局生效，次日不重复选入）。 */
export async function removeTradingAgentSelection(selectionId: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.admin.tradingAgentSelection(selectionId))
}
