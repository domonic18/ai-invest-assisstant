import { useQuery } from '@tanstack/react-query'

import { fetchWorkbench } from '@/api/workbench'
import { queryKeys } from './queryKeys'

/** 工作台五模块聚合；概览页 60s 内视为新鲜，不轮询。 */
export function useWorkbench() {
  return useQuery({
    queryKey: queryKeys.workbench.overview,
    queryFn: fetchWorkbench,
    staleTime: 60_000,
  })
}
