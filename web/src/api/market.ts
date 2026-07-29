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
  ApiMarketReviewGenerateRequest,
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

function mapIndexQuote(dto: ApiIndexQuoteResponse): IndexQuote {
  return {
    code: dto.code,
    name: dto.name,
    price: dto.price,
    change: dto.change,
    changePct: dto.change_pct,
    amount: dto.amount,
    trend: dto.trend,
  }
}

function mapIndexIntraday(dto: ApiIndexIntradayResponse): IndexIntraday {
  return {
    code: dto.code,
    name: dto.name,
    tradeDate: dto.trade_date,
    prevClose: dto.prev_close,
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

function mapMarketStats(dto: ApiMarketStatsResponse): MarketStats {
  return {
    tradeDate: dto.trade_date,
    amount: dto.amount,
    prevAmount: dto.prev_amount,
    amountChange: dto.amount_change,
    amountChangePct: dto.amount_change_pct,
    upCount: dto.up_count,
    downCount: dto.down_count,
    flatCount: dto.flat_count,
    limitUpCount: dto.limit_up_count,
    limitDownCount: dto.limit_down_count,
    brokenLimitCount: dto.broken_limit_count,
    emotionScore: dto.emotion_score,
    emotionLabel: dto.emotion_label,
    limitUpRatio: dto.limit_up_ratio,
    continuousRate: dto.continuous_rate,
    brokenRate: dto.broken_rate,
  }
}

function mapLimitUpStock(dto: ApiLimitUpItem): LimitUpStock {
  return {
    stockCode: dto.stock_code,
    stockName: dto.stock_name,
    changePct: dto.change_pct,
    latestPrice: dto.latest_price,
    sealedAmount: dto.sealed_amount,
    firstSealTime: dto.first_seal_time,
    lastSealTime: dto.last_seal_time,
    brokenLimitCount: dto.broken_limit_count,
    limitStatus: dto.limit_status,
    consecutiveBoards: dto.consecutive_boards,
    industry: dto.industry,
    sealType: dto.seal_type,
    themes: dto.themes,
  }
}

function mapLimitUpData(dto: ApiLimitUpResponse): LimitUpData {
  return {
    tradeDate: dto.trade_date,
    total: dto.total,
    firstBoard: dto.first_board,
    continuous: dto.continuous,
    maxBoards: dto.max_boards,
    ladder: dto.ladder.map(mapLimitUpStock),
    items: dto.items.map(mapLimitUpStock),
    groups: dto.groups.map((group) => ({
      name: group.name,
      count: group.count,
      changePct: group.change_pct,
      mainNetInflow: group.main_net_inflow,
      reason: group.reason,
      items: group.items.map(mapLimitUpStock),
    })),
    aiGenerated: dto.ai_generated,
  }
}

function mapSectorOverview(dto: ApiSectorOverviewResponse): SectorOverview {
  return {
    tradeDate: dto.trade_date,
    heatmap: dto.heatmap.map((item) => ({
      sectorName: item.sector_name,
      changePct: item.change_pct,
    })),
    topInflow: dto.top_inflow.map((item) => ({
      sectorName: item.sector_name,
      mainNetInflow: item.main_net_inflow,
      topStockName: item.top_stock_name,
    })),
    topOutflow: dto.top_outflow.map((item) => ({
      sectorName: item.sector_name,
      mainNetInflow: item.main_net_inflow,
      topStockName: item.top_stock_name,
    })),
    leading: dto.leading.map((item) => ({
      sectorName: item.sector_name,
      changePct: item.change_pct,
      limitUpCount: item.limit_up_count,
      mainNetInflow: item.main_net_inflow,
      topStockNames: item.top_stock_names,
    })),
  }
}

function mapWatchlistQuote(dto: ApiWatchlistQuoteItem): WatchlistQuote {
  return {
    code: dto.code,
    name: dto.name,
    price: dto.price,
    changePct: dto.change_pct,
    amount: dto.amount,
    tags: dto.tags,
    updatedAt: dto.updated_at,
  }
}

function mapMarketReview(dto: ApiMarketReviewResponse): MarketReview {
  return {
    tradeDate: dto.trade_date,
    sections: dto.sections.map((section) => ({
      key: section.key,
      title: section.title,
      content: section.content,
    })),
    model: dto.model,
    generatedAt: dto.generated_at,
    cached: dto.cached,
    edited: dto.edited,
  }
}

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
    ENDPOINTS.market.indexIntraday(code),
    { params: { trade_date: tradeDate } },
  )
  return mapIndexIntraday(response.data)
}

export async function fetchIndexKline(
  code: string,
  period: IndexKlinePeriod,
  limit = 250,
): Promise<IndexKline> {
  const response = await apiClient.get<ApiIndexKlineResponse>(
    ENDPOINTS.market.indexKline(code),
    { params: { period, limit } },
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
  return { tradeDate: response.data.trade_date, series: response.data.series }
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

const LLM_GENERATION_TIMEOUT = 300_000

/** 触发 LLM 生成 AI 复盘（regenerate=true 强制重新生成）。 */
export async function generateMarketReview(
  regenerate = false,
  tradeDate?: string,
): Promise<MarketReview> {
  const body: ApiMarketReviewGenerateRequest = {
    trade_date: tradeDate,
    regenerate,
  }
  const response = await apiClient.post<ApiMarketReviewResponse>(
    ENDPOINTS.market.aiReview,
    body,
    { timeout: LLM_GENERATION_TIMEOUT },
  )
  return mapMarketReview(response.data)
}

/** 按分区保存人工编辑后的复盘内容（sectionKey 为后端 prompt YAML 声明的分区键）。 */
export async function saveMarketReviewSection(
  tradeDate: string,
  sectionKey: string,
  content: string,
): Promise<MarketReview> {
  const body: ApiMarketReviewUpdateRequest = {
    trade_date: tradeDate,
    section_key: sectionKey,
    content,
  }
  const response = await apiClient.put<ApiMarketReviewResponse>(
    ENDPOINTS.market.aiReview,
    body,
  )
  return mapMarketReview(response.data)
}

/** 触发 LLM 生成 AI 涨停归因（regenerate=true 强制重新生成），返回完整涨停数据。 */
export async function generateLimitUpAttribution(
  regenerate = false,
  tradeDate?: string,
): Promise<LimitUpData> {
  const body: ApiMarketReviewGenerateRequest = {
    trade_date: tradeDate,
    regenerate,
  }
  const response = await apiClient.post<ApiLimitUpResponse>(
    ENDPOINTS.market.limitUpAiReview,
    body,
    { timeout: LLM_GENERATION_TIMEOUT },
  )
  return mapLimitUpData(response.data)
}

/** 补采指定交易日的行情数据（涨停池/炸板池/成交额）。 */
export async function collectMarketData(
  tradeDate: string,
): Promise<CollectTaskResult[]> {
  const body: ApiMarketCollectRequest = { trade_date: tradeDate }
  const response = await apiClient.post<ApiCollectTaskResult[]>(
    ENDPOINTS.market.collect,
    body,
  )
  return response.data.map((item) => ({
    task: item.task,
    status: item.status,
    itemsCollected: item.items_collected,
    errors: item.errors,
  }))
}
