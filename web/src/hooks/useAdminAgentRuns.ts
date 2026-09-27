import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { fetchAgentRunDetail, fetchAgentRuns, type AgentRunFilters } from '@/api/agentRunAdmin'

import { queryKeys } from './queryKeys'

/** Agent 执行会话列表（running 行存在时由调用方传 refetchInterval 轮询）。 */
export function useAdminAgentRuns(
  filters: AgentRunFilters,
  options?: { refetchInterval?: number },
) {
  return useQuery({
    queryKey: queryKeys.admin.agentRuns({ ...filters }),
    queryFn: () => fetchAgentRuns(filters),
    placeholderData: keepPreviousData,
    refetchInterval: options?.refetchInterval,
  })
}

/** 会话详情（含步骤时间线）。 */
export function useAdminAgentRunDetail(id: number | null) {
  return useQuery({
    queryKey: queryKeys.admin.agentRunDetail(id ?? 0),
    queryFn: () => fetchAgentRunDetail(id!),
    enabled: id !== null,
  })
}
