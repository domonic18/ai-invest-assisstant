import { useQuery } from '@tanstack/react-query'

import type { IndexKlinePeriod } from '@ai-invest/shared'
import {
  fetchIndexIntraday,
  fetchIndexKline,
  fetchLimitUp,
  fetchMarketIndices,
  fetchMarketReview,
  fetchMarketStats,
  fetchSectorOverview,
  fetchWatchlistQuotes,
} from '@/api/market'

const MARKET_KEY = ['market'] as const

const LIVE_REFETCH_INTERVAL = 60_000
const LIVE_STALE_TIME = 30_000

export function useMarketIndices(tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'indices', tradeDate],
    queryFn: () => fetchMarketIndices(tradeDate),
    staleTime: LIVE_STALE_TIME,
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
  })
}

export function useIndexIntraday(code: string, tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'intraday', code, tradeDate],
    queryFn: () => fetchIndexIntraday(code, tradeDate),
    staleTime: LIVE_STALE_TIME,
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
    retry: tradeDate ? false : 3,
  })
}

export function useIndexKline(code: string, period: IndexKlinePeriod) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'kline', code, period],
    queryFn: () => fetchIndexKline(code, period),
    staleTime: 5 * 60_000,
  })
}

export function useMarketStats(tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'stats', tradeDate],
    queryFn: () => fetchMarketStats(tradeDate),
    staleTime: LIVE_STALE_TIME,
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
  })
}

export function useLimitUp(tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'limit-up', tradeDate],
    queryFn: () => fetchLimitUp(tradeDate),
    staleTime: LIVE_STALE_TIME,
  })
}

export function useSectorOverview(tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'sectors', tradeDate],
    queryFn: () => fetchSectorOverview(tradeDate),
    staleTime: LIVE_STALE_TIME,
  })
}

export function useWatchlistQuotes() {
  return useQuery({
    queryKey: [...MARKET_KEY, 'watchlist-quotes'],
    queryFn: fetchWatchlistQuotes,
    staleTime: LIVE_STALE_TIME,
    refetchInterval: LIVE_REFETCH_INTERVAL,
  })
}

export function useMarketReview(enabled: boolean, tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'ai-review', tradeDate],
    queryFn: () => fetchMarketReview(false, tradeDate),
    enabled,
    staleTime: Infinity,
  })
}
