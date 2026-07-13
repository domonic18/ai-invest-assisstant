import { useQuery } from '@tanstack/react-query'

import { fetchKline, fetchStockDetail, searchStocks } from '@/api/stocks'

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

export function useKline(code: string, pageSize = 100) {
  return useQuery({
    queryKey: ['stocks', 'kline', code, pageSize],
    queryFn: () => fetchKline(code, { pageSize }),
    enabled: code.length > 0,
  })
}
