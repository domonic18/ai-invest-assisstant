import { useQuery } from '@tanstack/react-query'

import {
  fetchPaperTradeExecutions,
  fetchPaperTradeNav,
  fetchPaperTradeOrders,
  fetchPaperTradeOverview,
} from '@/api/paperTrade'
import { queryKeys } from '@/hooks/queryKeys'

export function usePaperTradeOverview() {
  return useQuery({
    queryKey: queryKeys.paperTrade.overview,
    queryFn: fetchPaperTradeOverview,
  })
}

export function usePaperTradeOrders(tradeDate?: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: queryKeys.paperTrade.orders(tradeDate, page, pageSize),
    queryFn: () => fetchPaperTradeOrders({ tradeDate, page, pageSize }),
  })
}

export function usePaperTradeExecutions(tradeDate?: string, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: queryKeys.paperTrade.executions(tradeDate, page, pageSize),
    queryFn: () => fetchPaperTradeExecutions({ tradeDate, page, pageSize }),
  })
}

export function usePaperTradeNav(days = 30) {
  return useQuery({
    queryKey: queryKeys.paperTrade.nav(days),
    queryFn: () => fetchPaperTradeNav(days),
  })
}
