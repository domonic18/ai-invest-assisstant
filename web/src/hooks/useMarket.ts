import { useQuery } from '@tanstack/react-query'

import {
  fetchIndexIntraday,
  fetchLimitUp,
  fetchMarketIndices,
  fetchMarketReview,
  fetchMarketStats,
  fetchSectorOverview,
  fetchWatchlistQuotes,
} from '@/api/market'

const MARKET_KEY = ['market'] as const

const LIVE_REFETCH_INTERVAL = 60_000

export function useMarketIndices(tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'indices', tradeDate],
    queryFn: () => fetchMarketIndices(tradeDate),
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
  })
}

export function useIndexIntraday(code: string, tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'intraday', code, tradeDate],
    queryFn: () => fetchIndexIntraday(code, tradeDate),
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
    retry: tradeDate ? false : 3,
  })
}

export function useMarketStats(tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'stats', tradeDate],
    queryFn: () => fetchMarketStats(tradeDate),
    refetchInterval: tradeDate ? false : LIVE_REFETCH_INTERVAL,
  })
}

export function useLimitUp(tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'limit-up', tradeDate],
    queryFn: () => fetchLimitUp(tradeDate),
  })
}

export function useSectorOverview(tradeDate?: string) {
  return useQuery({
    queryKey: [...MARKET_KEY, 'sectors', tradeDate],
    queryFn: () => fetchSectorOverview(tradeDate),
  })
}

export function useWatchlistQuotes() {
  return useQuery({
    queryKey: [...MARKET_KEY, 'watchlist-quotes'],
    queryFn: fetchWatchlistQuotes,
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
