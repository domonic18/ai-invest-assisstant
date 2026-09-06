import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiCollectTaskResult,
  ApiIndexIntradayResponse,
  ApiIndexKlineResponse,
  ApiIndexQuoteResponse,
  ApiLimitUpItem,
  ApiLimitUpIntradayResponse,
  ApiLimitUpResponse,
  ApiMarketCollectRequest,
  ApiMarketReviewResponse,
  ApiMarketReviewUpdateRequest,
  ApiMarketStatsResponse,
  ApiSectorOverviewResponse,
  ApiWatchlistQuoteItem,
  CollectTaskResult,
  IndexIntraday,
  IndexKline,
  IndexKlinePeriod,
  IndexQuote,
  LimitUpData,
  LimitUpIntraday,
  LimitUpStock,
  MarketReview,
  MarketStats,
  SectorOverview,
  WatchlistQuote,
} from '@ai-invest/shared'
import axios from 'axios'

import { apiClient } from './client'

export function mapIndexQuote(dto: ApiIndexQuoteResponse): IndexQuote {
  return {
    code: dto.code,
    name: dto.name,
    price: dto.price,
    change: dto.change,
    changePct: dto.changePct,
    amount: dto.amount,
    trend: dto.trend,
  }
}

function mapIndexIntraday(dto: ApiIndexIntradayResponse): IndexIntraday {
  return {
    code: dto.code,
    name: dto.name,
    tradeDate: dto.tradeDate,
    prevClose: dto.prevClose,
    points: dto.points,
  }
}

function mapIndexKline(dto: ApiIndexKlineResponse): IndexKline {
  return {
    code: dto.code,
    name: dto.name,
    period: dto.period as IndexKlinePeriod,
    bars: dto.bars,
  }
}

export function mapMarketStats(dto: ApiMarketStatsResponse): MarketStats {
  return {
    tradeDate: dto.tradeDate,
    amount: dto.amount,
    prevAmount: dto.prevAmount,
    amountChange: dto.amountChange,
    amountChangePct: dto.amountChangePct,
    upCount: dto.upCount,
    downCount: dto.downCount,
    flatCount: dto.flatCount,
    limitUpCount: dto.limitUpCount,
    limitDownCount: dto.limitDownCount,
    brokenLimitCount: dto.brokenLimitCount,
    emotionScore: dto.emotionScore,
    emotionLabel: dto.emotionLabel,
    limitUpRatio: dto.limitUpRatio,
    continuousRate: dto.continuousRate,
    brokenRate: dto.brokenRate,
  }
}

function mapLimitUpStock(dto: ApiLimitUpItem): LimitUpStock {
  return {
    stockCode: dto.stockCode,
    stockName: dto.stockName,
    changePct: dto.changePct,
    latestPrice: dto.latestPrice,
    sealedAmount: dto.sealedAmount,
    firstSealTime: dto.firstSealTime,
    lastSealTime: dto.lastSealTime,
    brokenLimitCount: dto.brokenLimitCount,
    limitStatus: dto.limitStatus,
    consecutiveBoards: dto.consecutiveBoards,
    industry: dto.industry,
    sealType: dto.sealType,
    themes: dto.themes,
  }
}

function mapLimitUpData(dto: ApiLimitUpResponse): LimitUpData {
  return {
    tradeDate: dto.tradeDate,
    total: dto.total,
    firstBoard: dto.firstBoard,
    continuous: dto.continuous,
    maxBoards: dto.maxBoards,
    ladder: dto.ladder.map(mapLimitUpStock),
    items: dto.items.map(mapLimitUpStock),
    groups: dto.groups.map((group) => ({
      name: group.name,
      count: group.count,
      changePct: group.changePct,
      mainNetInflow: group.mainNetInflow,
      reason: group.reason,
      items: group.items.map(mapLimitUpStock),
    })),
    aiGenerated: dto.aiGenerated,
  }
}

function mapSectorOverview(dto: ApiSectorOverviewResponse): SectorOverview {
  return {
    tradeDate: dto.tradeDate,
    heatmap: dto.heatmap.map((item) => ({
      sectorName: item.sectorName,
      changePct: item.changePct,
    })),
    topInflow: dto.topInflow.map((item) => ({
      sectorName: item.sectorName,
      mainNetInflow: item.mainNetInflow,
      topStockName: item.topStockName,
    })),
    topOutflow: dto.topOutflow.map((item) => ({
      sectorName: item.sectorName,
      mainNetInflow: item.mainNetInflow,
      topStockName: item.topStockName,
    })),
    leading: dto.leading.map((item) => ({
      sectorName: item.sectorName,
      changePct: item.changePct,
      limitUpCount: item.limitUpCount,
      mainNetInflow: item.mainNetInflow,
      topStockNames: item.topStockNames,
    })),
  }
}

export function mapWatchlistQuote(dto: ApiWatchlistQuoteItem): WatchlistQuote {
  return {
    code: dto.code,
    name: dto.name,
    price: dto.price,
    changePct: dto.changePct,
    amount: dto.amount,
    tags: dto.tags,
    updatedAt: dto.updatedAt,
    trend: dto.trend ?? [],
  }
}

export function mapMarketReview(dto: ApiMarketReviewResponse): MarketReview {
  return {
    tradeDate: dto.tradeDate,
    sections: dto.sections.map((section) => ({
      key: section.key,
      title: section.title,
      content: section.content,
    })),
    model: dto.model,
    generatedAt: dto.generatedAt,
    cached: dto.cached,
    edited: dto.edited,
  }
}

export async function fetchMarketIndices(
  tradeDate?: string,
): Promise<IndexQuote[]> {
  const response = await apiClient.get<ApiIndexQuoteResponse[]>(
    ENDPOINTS.market.indices,
    { params: { tradeDate: tradeDate } },
  )
  return response.data.map(mapIndexQuote)
}

export async function fetchIndexIntraday(
  code: string,
  tradeDate?: string,
): Promise<IndexIntraday> {
  const response = await apiClient.get<ApiIndexIntradayResponse>(
    ENDPOINTS.market.indexIntraday,
    { params: { code, tradeDate: tradeDate } },
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
    { params: { tradeDate: tradeDate } },
  )
  return mapMarketStats(response.data)
}

export async function fetchLimitUp(tradeDate?: string): Promise<LimitUpData> {
  const response = await apiClient.get<ApiLimitUpResponse>(
    ENDPOINTS.market.limitUp,
    { params: { tradeDate: tradeDate } },
  )
  return mapLimitUpData(response.data)
}

export async function fetchLimitUpIntraday(
  tradeDate?: string,
): Promise<LimitUpIntraday> {
  const response = await apiClient.get<ApiLimitUpIntradayResponse>(
    ENDPOINTS.market.limitUpIntraday,
    { params: { tradeDate: tradeDate } },
  )
  return { tradeDate: response.data.tradeDate, series: response.data.series }
}

export async function fetchSectorOverview(
  tradeDate?: string,
): Promise<SectorOverview> {
  const response = await apiClient.get<ApiSectorOverviewResponse>(
    ENDPOINTS.market.sectors,
    { params: { tradeDate: tradeDate } },
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
      { params: { tradeDate: tradeDate } },
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
  return response.data.map((item) => ({
    task: item.task,
    status: item.status,
    itemsCollected: item.itemsCollected,
    errors: item.errors,
  }))
}
