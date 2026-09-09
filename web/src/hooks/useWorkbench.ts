import { useQuery } from '@tanstack/react-query'

import { fetchReviewStatus, fetchWorkbench } from '@/api/workbench'
import { queryKeys } from './queryKeys'

/** 工作台五模块聚合；概览页 60s 内视为新鲜，不轮询。 */
export function useWorkbench() {
  return useQuery({
    queryKey: queryKeys.workbench.overview,
    queryFn: fetchWorkbench,
    staleTime: 60_000,
  })
}

/** 侧边栏复盘状态块；60s 轮询驱动倒计时刷新。 */
export function useReviewStatus() {
  return useQuery({
    queryKey: queryKeys.workbench.reviewStatus,
    queryFn: fetchReviewStatus,
    staleTime: 60_000,
    refetchInterval: 60_000,
  })
}
