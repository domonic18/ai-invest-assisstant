import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiAgentRunDetail, ApiAgentRunListResponse } from '@ai-invest/shared'

import { apiClient } from './client'

export interface AgentRunFilters {
  page?: number
  pageSize?: number
  agentKey?: string | null
  kind?: string | null
  period?: string | null
  status?: string | null
  triggerType?: string | null
  /** 基准交易日（YYYY-MM-DD），闭区间。 */
  tradeDateStart?: string | null
  tradeDateEnd?: string | null
}

export async function fetchAgentRuns(
  filters: AgentRunFilters = {},
): Promise<ApiAgentRunListResponse> {
  const { data } = await apiClient.get<ApiAgentRunListResponse>(ENDPOINTS.admin.agentRuns, {
    params: {
      page: filters.page ?? 1,
      page_size: filters.pageSize ?? 20,
      agent_key: filters.agentKey || undefined,
      kind: filters.kind || undefined,
      period: filters.period || undefined,
      status: filters.status || undefined,
      trigger_type: filters.triggerType || undefined,
      trade_date_start: filters.tradeDateStart || undefined,
      trade_date_end: filters.tradeDateEnd || undefined,
    },
  })
  return data
}

export async function fetchAgentRunDetail(id: number): Promise<ApiAgentRunDetail> {
  const { data } = await apiClient.get<ApiAgentRunDetail>(ENDPOINTS.admin.agentRun(id))
  return data
}
