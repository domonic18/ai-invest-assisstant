import { useQuery } from '@tanstack/react-query'

import type { AnomalySectorType } from '@ai-invest/shared'

import {
  fetchSectorAnomalyBoard,
  fetchSectorDetail,
  fetchStockAnomalyBoard,
} from '@/api/anomaly'
import { queryKeys } from '@/hooks/queryKeys'

/** 板块异动榜（tradeDate 缺省取最新检测日）。 */
export function useSectorAnomalyBoard(tradeDate?: string, sectorType?: AnomalySectorType) {
  return useQuery({
    queryKey: queryKeys.anomaly.sector(tradeDate, sectorType),
    queryFn: () => fetchSectorAnomalyBoard(tradeDate, sectorType),
  })
}

/** 个股异动榜（命中自选股带标注）。 */
export function useStockAnomalyBoard(tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.anomaly.stock(tradeDate),
    queryFn: () => fetchStockAnomalyBoard(tradeDate),
  })
}

/** 板块详情（K 线走势 + 资金流 + 异动日）。 */
export function useSectorDetail(sectorType: AnomalySectorType, sectorCode: string) {
  return useQuery({
    queryKey: queryKeys.sectorDetail(sectorType, sectorCode),
    queryFn: () => fetchSectorDetail(sectorType, sectorCode),
  })
}
