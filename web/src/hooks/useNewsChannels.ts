import { useQuery } from '@tanstack/react-query'

import { fetchNewsChannels } from '@/api/news'
import { queryKeys } from '@/hooks/queryKeys'

/** 渠道状态变化缓慢（分钟级），60s 轮询足够感知断流/恢复。 */
export const NEWS_CHANNELS_REFETCH_INTERVAL = 60_000

/** 资讯渠道监控卡 + 今日统计。 */
export function useNewsChannels() {
  return useQuery({
    queryKey: queryKeys.news.channels,
    queryFn: fetchNewsChannels,
    refetchInterval: NEWS_CHANNELS_REFETCH_INTERVAL,
  })
}
