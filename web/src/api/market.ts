import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiIndexIntradayResponse,
  ApiIndexQuoteResponse,
  ApiLimitUpItem,
  ApiLimitUpResponse,
  ApiMarketReviewResponse,
  ApiMarketStatsResponse,
  ApiSectorOverviewResponse,
  ApiWatchlistQuoteItem,
  IndexIntraday,
  IndexQuote,
  LimitUpData,
  LimitUpStock,
  MarketReview,
  MarketStats,
  SectorOverview,
  WatchlistQuote,
} from '@ai-invest/shared'

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
    brokenCount: dto.broken_count,
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
    breakCount: dto.break_count,
    limitStat: dto.limit_stat,
    consecutiveBoards: dto.consecutive_boards,
    industry: dto.industry,
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
    overview: dto.overview,
    emotionAnalysis: dto.emotion_analysis,
    capitalAnalysis: dto.capital_analysis,
    riskAdvice: dto.risk_advice,
    model: dto.model,
    generatedAt: dto.generated_at,
    cached: dto.cached,
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

export async function fetchMarketReview(
  regenerate = false,
  tradeDate?: string,
): Promise<MarketReview> {
  const response = await apiClient.get<ApiMarketReviewResponse>(
    ENDPOINTS.market.aiReview,
    { params: { regenerate, trade_date: tradeDate } },
  )
  return mapMarketReview(response.data)
}
