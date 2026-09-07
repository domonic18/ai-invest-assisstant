import { useQuery } from '@tanstack/react-query'

import type { IndexKlinePeriod } from '@ai-invest/shared'
import {
  fetchIndexIntraday,
  fetchIndexKline,
  fetchLimitUp,
  fetchLimitUpIntraday,
  fetchMarketIndices,
  fetchMarketReview,
  fetchMarketStats,
  fetchSectorOverview,
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

export function useIndexKline(code: string, period: IndexKlinePeriod) {
  return useQuery({
    queryKey: queryKeys.market.kline(code, period),
    queryFn: () => fetchIndexKline(code, period),
    staleTime: 5 * 60_000,
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
