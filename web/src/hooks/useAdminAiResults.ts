import type { QueryClient } from '@tanstack/react-query'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { AdminAiResultListParams } from '@ai-invest/shared'

import {
  deleteAdminAiResult,
  fetchAdminAiResultDetail,
  fetchAdminAiResults,
  fetchAiResultSkills,
} from '@/api/adminAiResults'
import { queryKeys } from '@/hooks/queryKeys'

/** 删除/重新生成后需联动失效的用户侧缓存前缀（按 skill_id；未登记的 skill 仅失效管理列表）。 */
const USER_SIDE_QUERY_KEYS: Record<string, readonly unknown[]> = {
  'market-daily-review': queryKeys.market.all,
  'limit-up-review': queryKeys.market.all,
  'stock-daily-analysis': queryKeys.stocks.all,
  'industry-chain-analysis': queryKeys.chain.all,
}

export function useAiResultSkills() {
  return useQuery({
    queryKey: queryKeys.admin.aiResultSkills,
    queryFn: fetchAiResultSkills,
    staleTime: 5 * 60 * 1000,
  })
}

export function useAdminAiResults(params: AdminAiResultListParams, enabled = true) {
  return useQuery({
    queryKey: [...queryKeys.admin.aiResults, params] as const,
    queryFn: () => fetchAdminAiResults(params),
    enabled,
  })
}

export function useAdminAiResultDetail(id: number | null) {
  return useQuery({
    queryKey: [...queryKeys.admin.aiResults, 'detail', id] as const,
    queryFn: () => fetchAdminAiResultDetail(id as number),
    enabled: id !== null,
  })
}

/** 管理列表 + 对应 skill 的用户侧缓存一并失效（删除与 AI 生成完成共用）。 */
export function invalidateAiResultCaches(queryClient: QueryClient, skillId?: string) {
  void queryClient.invalidateQueries({ queryKey: queryKeys.admin.aiResults })
  const userKey = skillId ? USER_SIDE_QUERY_KEYS[skillId] : undefined
  if (userKey) void queryClient.invalidateQueries({ queryKey: userKey })
}

export function useDeleteAdminAiResult() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id }: { id: number; skillId: string }) => deleteAdminAiResult(id),
    onSuccess: (_result, { skillId }) => invalidateAiResultCaches(queryClient, skillId),
  })
}
