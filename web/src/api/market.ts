import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiCollectTaskResult,
  ApiIndexIntradayResponse,
  ApiIndexKlineResponse,
  ApiIndexQuoteResponse,
  ApiLimitUpIntradayResponse,
  ApiLimitUpResponse,
  ApiMarketCollectRequest,
  ApiMarketReviewResponse,
  ApiMarketReviewUpdateRequest,
  ApiMarketStatsResponse,
  ApiSectorOverviewResponse,
  ApiWatchlistQuoteItem,
  CollectTaskResult,
  FedWatchResponse,
  GlobalIndexHistoryPoint,
  GlobalIndexQuote,
  IndexIntraday,
  IndexKline,
  IndexKlinePeriod,
  IndexQuote,
  LimitUpData,
  LimitUpIntraday,
  MarketReview,
  MarketStats,
  SectorOverview,
  SectorQuoteResponse,
  WatchlistQuote,
} from '@ai-invest/shared'
import axios from 'axios'

import { apiClient } from './client'
import {
  mapCollectTaskResult,
  mapIndexIntraday,
  mapIndexKline,
  mapIndexQuote,
  mapLimitUpData,
  mapMarketReview,
  mapMarketStats,
  mapSectorOverview,
  mapWatchlistQuote,
} from './mappers/market'

export async function fetchMarketIndices(
  tradeDate?: string,
): Promise<IndexQuote[]> {
  const response = await apiClient.get<ApiIndexQuoteResponse[]>(
    ENDPOINTS.market.indices,
    { params: { trade_date: tradeDate } },
  )
  return response.data.map(mapIndexQuote)
}

export async function fetchIndexIntraday(
  code: string,
  tradeDate?: string,
): Promise<IndexIntraday> {
  const response = await apiClient.get<ApiIndexIntradayResponse>(
    ENDPOINTS.market.indexIntraday,
    { params: { code, trade_date: tradeDate } },
  )
  return mapIndexIntraday(response.data)
}

export async function fetchIndexKline(
  code: string,
  period: IndexKlinePeriod,
  limit = 250,
): Promise<IndexKline> {
  const response = await apiClient.get<ApiIndexKlineResponse>(
    ENDPOINTS.market.indexKline,
    { params: { code, period, limit } },
  )
  return mapIndexKline(response.data)
}

export async function fetchMarketStats(tradeDate?: string): Promise<MarketStats> {
  const response = await apiClient.get<ApiMarketStatsResponse>(
    ENDPOINTS.market.stats,
    { params: { trade_date: tradeDate } },
  )
  return mapMarketStats(response.data)
}

export async function fetchLimitUp(tradeDate?: string): Promise<LimitUpData> {
  const response = await apiClient.get<ApiLimitUpResponse>(
    ENDPOINTS.market.limitUp,
    { params: { trade_date: tradeDate } },
  )
  return mapLimitUpData(response.data)
}

export async function fetchLimitUpIntraday(
  tradeDate?: string,
): Promise<LimitUpIntraday> {
  const response = await apiClient.get<ApiLimitUpIntradayResponse>(
    ENDPOINTS.market.limitUpIntraday,
    { params: { trade_date: tradeDate } },
  )
  return { tradeDate: response.data.tradeDate, series: response.data.series }
}

export async function fetchSectorOverview(
  tradeDate?: string,
): Promise<SectorOverview> {
  const response = await apiClient.get<ApiSectorOverviewResponse>(
    ENDPOINTS.market.sectors,
    { params: { trade_date: tradeDate } },
  )
  return mapSectorOverview(response.data)
}

export async function fetchWatchlistQuotes(): Promise<WatchlistQuote[]> {
  const response = await apiClient.get<ApiWatchlistQuoteItem[]>(
    ENDPOINTS.users.watchlistQuotes,
  )
  return response.data.map(mapWatchlistQuote)
}

/** 指定日期不是交易日（每日复盘只对交易日有效）。 */
export class NonTradingDayError extends Error {}

/** 只读取已生成的 AI 复盘；不存在时（204）返回 null（不会触发生成）。 */
export async function fetchMarketReview(
  tradeDate?: string,
): Promise<MarketReview | null> {
  try {
    const response = await apiClient.get<ApiMarketReviewResponse>(
      ENDPOINTS.market.aiReview,
      { params: { trade_date: tradeDate } },
    )
    if (response.status === 204) {
      return null
    }
    return mapMarketReview(response.data)
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 400) {
      const detail = (error.response.data as { detail?: string } | undefined)
        ?.detail
      throw new NonTradingDayError(detail ?? '该日不是交易日')
    }
    throw error
  }
}

/** 按分区保存人工编辑后的复盘内容（sectionKey 为后端 prompt YAML 声明的分区键）。 */
export async function saveMarketReviewSection(
  tradeDate: string,
  sectionKey: string,
  content: string,
): Promise<MarketReview> {
  const body: ApiMarketReviewUpdateRequest = {
    tradeDate: tradeDate,
    sectionKey: sectionKey,
    content,
  }
  const response = await apiClient.put<ApiMarketReviewResponse>(
    ENDPOINTS.market.aiReview,
    body,
  )
  return mapMarketReview(response.data)
}

/** 补采指定交易日的行情数据（涨停池/炸板池/成交额）。 */
export async function collectMarketData(
  tradeDate: string,
): Promise<CollectTaskResult[]> {
  const body: ApiMarketCollectRequest = { tradeDate: tradeDate }
  const response = await apiClient.post<ApiCollectTaskResult[]>(
    ENDPOINTS.market.collect,
    body,
  )
  return response.data.map(mapCollectTaskResult)
}

export async function fetchGlobalIndices(): Promise<GlobalIndexQuote[]> {
  const response = await apiClient.get<GlobalIndexQuote[]>(
    ENDPOINTS.market.globalIndices,
  )
  return response.data
}

export async function fetchGlobalIndexHistory(
  indexCode: string,
  months = 12,
): Promise<GlobalIndexHistoryPoint[]> {
  const response = await apiClient.get<GlobalIndexHistoryPoint[]>(
    ENDPOINTS.market.globalIndexHistory,
    { params: { index_code: indexCode, months } },
  )
  return response.data
}

export async function fetchGlobalIndexKline(
  indexCode: string,
  period: IndexKlinePeriod,
  limit = 250,
): Promise<IndexKline> {
  const response = await apiClient.get<ApiIndexKlineResponse>(
    ENDPOINTS.market.globalIndexKline,
    { params: { index_code: indexCode, period, limit } },
  )
  return mapIndexKline(response.data)
}

export async function fetchFedWatch(): Promise<FedWatchResponse | null> {
  const response = await apiClient.get<FedWatchResponse | null>(
    ENDPOINTS.market.fedWatch,
  )
  return response.data ?? null
}

export async function fetchSectorQuotes(
  sectorType: string,
): Promise<SectorQuoteResponse | null> {
  const response = await apiClient.get<SectorQuoteResponse | null>(
    ENDPOINTS.market.sectorQuotes,
    { params: { sector_type: sectorType } },
  )
  return response.data ?? null
}
