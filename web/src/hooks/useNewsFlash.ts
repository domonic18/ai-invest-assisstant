import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { fetchNewsFlash } from '@/api/news'
import { mapNewsFlashPage } from '@/api/mappers/news'
import { queryKeys } from '@/hooks/queryKeys'

/** 东财快讯 30 分钟 cron 落库，30s 轮询即足够及时。 */
export const NEWS_FLASH_REFETCH_INTERVAL = 30_000

/** 分页查询东财快讯；autoRefresh 时按 30s 轮询。 */
export function useNewsFlash(
  page: number,
  pageSize: number,
  autoRefresh = true,
) {
  return useQuery({
    queryKey: queryKeys.news.flash(page, pageSize),
    queryFn: async () => {
      const data = await fetchNewsFlash({ page, pageSize })
      return mapNewsFlashPage(data)
    },
    placeholderData: keepPreviousData,
    refetchInterval: autoRefresh ? NEWS_FLASH_REFETCH_INTERVAL : false,
  })
}
