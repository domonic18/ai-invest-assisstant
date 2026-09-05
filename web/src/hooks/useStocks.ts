import { useQuery } from '@tanstack/react-query'

import {
  fetchKline,
  fetchStockAiAnalysisDates,
  fetchStockAiAnalysisStatus,
  fetchStockDetail,
  fetchStockIntraday,
  fetchStockKline,
  fetchStockQuote,
  fetchStockSectors,
  searchStocks,
  type StockKlineParams,
} from '@/api/stocks'
import { queryKeys } from './queryKeys'

// 当前交易日实时数据：30s 内视为新鲜，避免反复打详情接口
const LIVE_STALE_TIME = 30_000
// 当日 K 线/分时：盘中变化但短期无需高频刷新
const INTRADAY_STALE_TIME = 5 * 60_000
// 个股基础信息（名称/板块归属/描述）：盘后基本不变
const DETAIL_STALE_TIME = 30 * 60_000

export function useStockSearch(q: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.stocks.search(q),
    queryFn: () => searchStocks({ q, limit: 20 }),
    enabled: enabled && q.length > 0,
  })
}

export function useStockDetail(code: string) {
  return useQuery({
    queryKey: queryKeys.stocks.detail(code),
    queryFn: () => fetchStockDetail(code),
    enabled: code.length > 0,
    staleTime: DETAIL_STALE_TIME,
  })
}

export function useStockQuote(code: string) {
  return useQuery({
    queryKey: queryKeys.stocks.quote(code),
    queryFn: () => fetchStockQuote(code),
    enabled: code.length > 0,
    staleTime: LIVE_STALE_TIME,
    refetchInterval: 30_000,
  })
}

export function useStockKline(code: string, params: StockKlineParams = {}) {
  return useQuery({
    queryKey: queryKeys.stocks.kline(code, params.period, params.limit),
    queryFn: () => fetchStockKline(code, params),
    enabled: code.length > 0,
    staleTime: INTRADAY_STALE_TIME,
  })
}

export function useStockIntraday(code: string, tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.stocks.intraday(code, tradeDate),
    queryFn: () => fetchStockIntraday(code, tradeDate),
    enabled: code.length > 0,
    // 历史日期分时不变；当日盘中 30s 视为新鲜
    staleTime: tradeDate ? Infinity : LIVE_STALE_TIME,
  })
}

export function useStockSectors(code: string) {
  return useQuery({
    queryKey: queryKeys.stocks.sectors(code),
    queryFn: () => fetchStockSectors(code),
    enabled: code.length > 0,
    staleTime: DETAIL_STALE_TIME,
  })
}

export function useKline(code: string, pageSize = 100) {
  return useQuery({
    queryKey: queryKeys.stocks.klinePaged(code, pageSize),
    queryFn: () => fetchKline(code, { pageSize }),
    enabled: code.length > 0,
    staleTime: INTRADAY_STALE_TIME,
  })
}

/** 个股 AI 分析状态：ready 含数据，running 表示定时任务生成中，none 无结果。 */
export function useStockAiAnalysis(code: string, tradeDate?: string) {
  return useQuery({
    queryKey: queryKeys.stocks.aiAnalysis(code, tradeDate),
    queryFn: () => fetchStockAiAnalysisStatus(code, tradeDate),
    enabled: code.length > 0,
    staleTime: 10 * 60_000,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 3000 : false),
  })
}

/** 该股已生成分析的全部交易日（升序），供日历标记有记录的日期。 */
export function useStockAiAnalysisDates(code: string) {
  return useQuery({
    queryKey: queryKeys.stocks.aiAnalysisDates(code),
    queryFn: () => fetchStockAiAnalysisDates(code),
    enabled: code.length > 0,
    staleTime: 10 * 60_000,
  })
}
