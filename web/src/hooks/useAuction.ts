import { useQuery } from '@tanstack/react-query'

import { fetchIndexAuctionTrend } from '@/api/auction'
import type { IndexAuctionTrendParams } from '@/api/auction'

export function useIndexAuctionTrend(params: IndexAuctionTrendParams = {}) {
  const { days = 30, startDate, endDate } = params
  return useQuery({
    queryKey: ['auction', 'index-trend', days, startDate, endDate],
    queryFn: () => fetchIndexAuctionTrend({ days, startDate, endDate }),
    // 采集在 9:26~9:29 完成，缓存不超过 5 分钟保证盘前能看到当日数据
    staleTime: 5 * 60_000,
  })
}
