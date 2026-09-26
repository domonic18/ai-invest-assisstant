/** 交易 Agent API（admin /admin/trading-agent/*，批次 5 配置 + 批次 6 复盘）。 */

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiTradingAgentConfig,
  ApiTradingAgentConfigUpdateRequest,
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
): Promise<ApiTradingAgentReview> {
  const response = await apiClient.get<ApiTradingAgentReview>(
    ENDPOINTS.admin.tradingAgentReview,
    { params: { period } },
  )
  return response.data
}
