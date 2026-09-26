/** 交易 Agent 配置 API（admin /admin/trading-agent/config，批次 5）。 */

import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiTradingAgentConfig,
  ApiTradingAgentConfigUpdateRequest,
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
