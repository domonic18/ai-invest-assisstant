import { useQuery } from '@tanstack/react-query'

import { fetchHotspots, fetchLatestDaySectors, type HotspotParams } from '@/api/hotspot'

import { queryKeys } from '@/hooks/queryKeys'

const HOTSPOT_KEY = queryKeys.hotspot

/** 原型口径：热点页板块数据 5 分钟自动刷新。 */
const HOTSPOT_REFETCH_INTERVAL = 5 * 60_000

export function useHotspot(params: HotspotParams = {}) {
  return useQuery({
    queryKey: [...HOTSPOT_KEY, params],
    queryFn: () => fetchHotspots(params),
    refetchInterval: HOTSPOT_REFETCH_INTERVAL,
  })
}

/** 最新有数据交易日的完整板块清单（话题云 / 信号卡共用，5 分钟自动刷新）。 */
export function useLatestDaySectors() {
  return useQuery({
    queryKey: [...HOTSPOT_KEY, 'latest-day'],
    queryFn: () => fetchLatestDaySectors(),
    refetchInterval: HOTSPOT_REFETCH_INTERVAL,
  })
}
