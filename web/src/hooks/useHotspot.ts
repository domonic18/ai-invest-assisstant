import { useQuery } from '@tanstack/react-query'

import { fetchHotspots, type HotspotParams } from '@/api/hotspot'

const HOTSPOT_KEY = ['hotspot'] as const

export function useHotspot(params: HotspotParams = {}) {
  return useQuery({
    queryKey: [...HOTSPOT_KEY, params],
    queryFn: () => fetchHotspots(params),
  })
}
