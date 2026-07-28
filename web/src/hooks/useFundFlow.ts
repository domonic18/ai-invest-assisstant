import { useQuery } from '@tanstack/react-query'

import { fetchSectorFundFlowTrend } from '@/api/fundFlow'
import type { SectorType } from '@/api/fundFlow'

import { queryKeys } from './queryKeys'

export function useSectorFundFlowTrend(sectorType: SectorType, days: number) {
  return useQuery({
    queryKey: queryKeys.fundFlow.sectorTrend(sectorType, days),
    queryFn: () => fetchSectorFundFlowTrend(sectorType, days),
    // 板块资金流向为盘后 17:30 采集，30 分钟内数据不变
    staleTime: 30 * 60_000,
  })
}
