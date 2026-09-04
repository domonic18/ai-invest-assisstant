import { useQuery } from '@tanstack/react-query'

import { fetchHotspots, type HotspotParams } from '@/api/hotspot'

const HOTSPOT_KEY = ['hotspot'] as const

/** 原型口径：热点页板块数据 5 分钟自动刷新。 */
const HOTSPOT_REFETCH_INTERVAL = 5 * 60_000

export function useHotspot(params: HotspotParams = {}) {
  return useQuery({
    queryKey: [...HOTSPOT_KEY, params],
    queryFn: () => fetchHotspots(params),
    refetchInterval: HOTSPOT_REFETCH_INTERVAL,
  })
}
