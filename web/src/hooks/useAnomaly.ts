import { useQuery } from '@tanstack/react-query'

import type { AnomalySectorType } from '@ai-invest/shared'

import {
  fetchSectorAnomalyBoard,
  fetchSectorAnomalyDates,
  fetchSectorDetail,
  fetchStockAnomalyBoard,
  fetchStockAnomalyDates,
} from '@/api/anomaly'
import { queryKeys } from '@/hooks/queryKeys'

/** 有板块异动检测数据的交易日（升序），供日历打点。 */
export function useSectorAnomalyDates() {
  return useQuery({
    queryKey: queryKeys.anomaly.sectorDates,
    queryFn: fetchSectorAnomalyDates,
    staleTime: 5 * 60 * 1000,
  })
}

/** 有个股异动检测数据的交易日（升序），供日历打点。 */
export function useStockAnomalyDates() {
  return useQuery({
    queryKey: queryKeys.anomaly.stockDates,
    queryFn: fetchStockAnomalyDates,
    staleTime: 5 * 60 * 1000,
  })
}

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
