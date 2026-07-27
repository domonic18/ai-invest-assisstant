import { useQuery } from '@tanstack/react-query'

import {
  fetchKline,
  fetchStockDetail,
  fetchStockIntraday,
  fetchStockKline,
  fetchStockQuote,
  fetchStockSectors,
  searchStocks,
  type StockKlineParams,
} from '@/api/stocks'

export function useStockSearch(q: string, enabled = true) {
  return useQuery({
    queryKey: ['stocks', 'search', q],
    queryFn: () => searchStocks({ q, limit: 20 }),
    enabled: enabled && q.length > 0,
  })
}

export function useStockDetail(code: string) {
  return useQuery({
    queryKey: ['stocks', 'detail', code],
    queryFn: () => fetchStockDetail(code),
    enabled: code.length > 0,
  })
}

export function useStockQuote(code: string) {
  return useQuery({
    queryKey: ['stocks', 'quote', code],
    queryFn: () => fetchStockQuote(code),
    enabled: code.length > 0,
    refetchInterval: 30_000,
  })
}

export function useStockKline(code: string, params: StockKlineParams = {}) {
  return useQuery({
    queryKey: ['stocks', 'kline', code, params.period, params.limit],
    queryFn: () => fetchStockKline(code, params),
    enabled: code.length > 0,
  })
}

export function useStockIntraday(code: string, tradeDate?: string) {
  return useQuery({
    queryKey: ['stocks', 'intraday', code, tradeDate],
    queryFn: () => fetchStockIntraday(code, tradeDate),
    enabled: code.length > 0,
  })
}

export function useStockSectors(code: string) {
  return useQuery({
    queryKey: ['stocks', 'sectors', code],
    queryFn: () => fetchStockSectors(code),
    enabled: code.length > 0,
  })
}

export function useKline(code: string, pageSize = 100) {
  return useQuery({
    queryKey: ['stocks', 'kline', code, pageSize],
    queryFn: () => fetchKline(code, { pageSize }),
    enabled: code.length > 0,
  })
}
