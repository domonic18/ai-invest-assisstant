import { useQuery } from '@tanstack/react-query'

import type { IndexKlinePeriod } from '@ai-invest/shared'
import {
  fetchFedWatch,
  fetchGlobalIndexHistory,
  fetchGlobalIndexKline,
  fetchGlobalIndices,
  fetchIndexIntraday,
  fetchIndexKline,
  fetchLimitUp,
  fetchLimitUpIntraday,
  fetchMarketIndices,
  fetchMarketReview,
  fetchMarketStats,
  fetchSectorOverview,
  fetchSectorQuotes,
  fetchWatchlistQuotes,
} from '@/api/market'
import { queryKeys } from '@/hooks/queryKeys'

const LIVE_REFETCH_INTERVAL = 60_000
const LIVE_STALE_TIME = 30_000

export function useMarketIndices(tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.market.indices(tradeDate),
    queryFn: () => fetchMarketIndices(tradeDate),
    staleTime: LIVE_STALE_TIME,
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
  })
}

export function useIndexIntraday(code: string, tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.market.intraday(code, tradeDate),
    queryFn: () => fetchIndexIntraday(code, tradeDate),
    staleTime: LIVE_STALE_TIME,
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
    retry: tradeDate ? false : 3,
  })
}

export function useIndexKline(code: string, period: IndexKlinePeriod, enabled = true) {
  return useQuery({
    queryKey: queryKeys.market.kline(code, period),
    queryFn: () => fetchIndexKline(code, period),
    staleTime: 5 * 60_000,
    enabled,
  })
}

export function useMarketStats(tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.market.stats(tradeDate),
    queryFn: () => fetchMarketStats(tradeDate),
    staleTime: LIVE_STALE_TIME,
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
  })
}

export function useLimitUp(tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.market.limitUp(tradeDate),
    queryFn: () => fetchLimitUp(tradeDate),
    staleTime: LIVE_STALE_TIME,
  })
}

export function useLimitUpIntraday(tradeDate?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.market.limitUpIntraday(tradeDate),
    queryFn: () => fetchLimitUpIntraday(tradeDate),
    staleTime: 5 * 60_000,
    enabled,
  })
}

export function useSectorOverview(tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.market.sectors(tradeDate),
    queryFn: () => fetchSectorOverview(tradeDate),
    staleTime: LIVE_STALE_TIME,
  })
}

export function useWatchlistQuotes() {
  return useQuery({
    queryKey: queryKeys.market.watchlistQuotes,
    queryFn: fetchWatchlistQuotes,
    staleTime: LIVE_STALE_TIME,
    refetchInterval: LIVE_REFETCH_INTERVAL,
  })
}

export function useMarketReview(tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.market.aiReview(tradeDate),
    queryFn: () => fetchMarketReview(tradeDate),
    staleTime: 5 * 60 * 1000,
  })
}

/** 全球指数实时快照（日频采集，5 分钟档）。 */
export function useGlobalIndices() {
  return useQuery({
    queryKey: queryKeys.market.globalIndices,
    queryFn: fetchGlobalIndices,
    staleTime: 5 * 60_000,
  })
}

/** 单一全球指标近 N 月收盘序列（宏观页 12 个月走势图 / 2s10s 利差）。 */
export function useGlobalIndexHistory(indexCode: string, months = 12, enabled = true) {
  return useQuery({
    queryKey: queryKeys.market.globalIndexHistory(indexCode, months),
    queryFn: () => fetchGlobalIndexHistory(indexCode, months),
    staleTime: 5 * 60_000,
    enabled,
  })
}

/** 全球指标多周期 K 线（详情页；含 OHLC 蜡烛与 close-only 收盘线两类源）。 */
export function useGlobalIndexKline(indexCode: string, period: IndexKlinePeriod) {
  return useQuery({
    queryKey: queryKeys.market.globalIndexKline(indexCode, period),
    queryFn: () => fetchGlobalIndexKline(indexCode, period),
    staleTime: 5 * 60_000,
  })
}

/** CME FedWatch 加息概率（每日一次快照）。 */
export function useFedWatch() {
  return useQuery({
    queryKey: queryKeys.market.fedWatch,
    queryFn: fetchFedWatch,
    staleTime: 5 * 60_000,
  })
}

/** 板块行情日快照（行业/概念，CapitalFlow 热力卡）。 */
export function useSectorQuotes(sectorType: string) {
  return useQuery({
    queryKey: queryKeys.market.sectorQuotes(sectorType),
    queryFn: () => fetchSectorQuotes(sectorType),
    staleTime: 5 * 60_000,
  })
}
