import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { mapTelegraphPage } from '@/api/mappers'
import { fetchTelegraph } from '@/api/telegraph'
import { queryKeys } from '@/hooks/queryKeys'

/** 电报近实时刷新间隔：collector-stream 每 10s 轮询一轮。 */
export const TELEGRAPH_REFETCH_INTERVAL = 10_000

/** 分页查询财联社电报；autoRefresh 时按 10s 轮询观察新电报到达。 */
export function useTelegraph(
  page: number,
  pageSize: number,
  minImportance?: number,
  autoRefresh = true,
) {
  return useQuery({
    queryKey: queryKeys.telegraph.list(page, pageSize, minImportance),
    queryFn: async () => {
      const data = await fetchTelegraph({ page, pageSize, minImportance })
      return mapTelegraphPage(data)
    },
    placeholderData: keepPreviousData,
    refetchInterval: autoRefresh ? TELEGRAPH_REFETCH_INTERVAL : false,
  })
}
