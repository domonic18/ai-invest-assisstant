import type {
  ApiAuctionDataResponse,
  ApiKlineDataResponse,
  ApiStockAiAnalysisResponse,
  ApiStockBasicResponse,
  ApiStockIntradayResponse,
  ApiStockKlineResponse,
  ApiStockQuoteResponse,
  ApiStockSectorsResponse,
  ApiWatchlistGroupWithItemsResponse,
  ApiWatchlistItemResponse,
} from '@ai-invest/shared'
import type {
  AuctionData,
  KlineData,
  Stock,
  StockAiAnalysis,
  StockIntraday,
  StockKline,
  StockQuote,
  StockSector,
  WatchlistGroup,
  WatchlistItem,
} from '@ai-invest/shared'

export function mapStock(dto: ApiStockBasicResponse): Stock {
  return {
    code: dto.stock_code,
    name: dto.stock_name,
    industry: dto.industry_level_1 || dto.industry_level_2 || dto.industry_level_3 || '',
    market: normalizeMarket(dto.market),
    fullName: dto.full_name,
    industryLevel1: dto.industry_level_1,
    industryLevel2: dto.industry_level_2,
    industryLevel3: dto.industry_level_3,
  }
}

function normalizeMarket(market: string): 'SH' | 'SZ' | 'BJ' {
  const upper = market.toUpperCase()
  if (upper === 'SH' || upper === 'SSE') return 'SH'
  if (upper === 'SZ' || upper === 'SZSE') return 'SZ'
  if (upper === 'BJ' || upper === 'BSE') return 'BJ'
  return 'SH'
}

export function mapKlineData(dto: ApiKlineDataResponse): KlineData {
  return {
    date: dto.trade_date,
    open: Number(dto.open),
    high: Number(dto.high),
    low: Number(dto.low),
    close: Number(dto.close),
    volume: Number(dto.volume),
    amount: Number(dto.amount),
  }
}

export function mapStockQuote(dto: ApiStockQuoteResponse): StockQuote {
  return {
    code: dto.code,
    name: dto.name,
    price: dto.price,
    prevClose: dto.prev_close,
    change: dto.change,
    changePct: dto.change_pct,
    open: dto.open,
    high: dto.high,
    low: dto.low,
    volume: dto.volume,
    amount: dto.amount,
    marketCap: dto.market_cap,
    circulatingMarketCap: dto.circulating_market_cap,
    updatedAt: dto.updated_at,
  }
}

export function mapStockKline(dto: ApiStockKlineResponse): StockKline {
  return {
    code: dto.code,
    name: dto.name,
    period: dto.period,
    bars: dto.bars.map((bar) => ({
      date: bar.date,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume,
      amount: bar.amount,
      changePct: bar.change_pct,
      amplitude: bar.amplitude,
      turnoverRate: bar.turnover_rate,
    })),
  }
}

export function mapIntraday(dto: ApiStockIntradayResponse): StockIntraday {
  return {
    code: dto.code,
    name: dto.name,
    tradeDate: dto.trade_date,
    prevClose: dto.prev_close,
    points: dto.points.map((point) => ({
      time: point.time,
      price: point.price,
      volume: point.volume,
      amount: point.amount,
    })),
  }
}

export function mapStockSector(dto: ApiStockSectorsResponse['sectors'][number]): StockSector {
  return {
    name: dto.name,
    type: dto.type,
    changePct: dto.change_pct,
    mainNetInflow: dto.main_net_inflow,
  }
}

export function mapStockSectors(dto: ApiStockSectorsResponse): {
  code: string
  name: string
  sectors: StockSector[]
} {
  return {
    code: dto.code,
    name: dto.name,
    sectors: dto.sectors.map(mapStockSector),
  }
}

export function mapAuctionData(dto: ApiAuctionDataResponse): AuctionData {
  return {
    date: dto.trade_date,
    time: dto.match_time,
    price: Number(dto.price),
    volume: Number(dto.volume),
    bidPrices: dto.bid_prices,
    bidVolumes: dto.bid_volumes,
    askPrices: dto.ask_prices,
    askVolumes: dto.ask_volumes,
  }
}

export function mapWatchlistItem(dto: ApiWatchlistItemResponse): WatchlistItem {
  return {
    id: String(dto.id),
    code: dto.stock_code,
    tags: dto.tags || [],
    groupId: dto.group_id,
    createdAt: dto.created_at,
  }
}

export function mapStockAiAnalysis(dto: ApiStockAiAnalysisResponse): StockAiAnalysis {
  return {
    stockCode: dto.stock_code,
    stockName: dto.stock_name,
    tradeDate: dto.trade_date,
    model: dto.model,
    generatedAt: dto.generated_at,
    cached: dto.cached,
    sections: dto.sections.map((section) => ({
      key: section.key,
      title: section.title,
      content: section.content,
    })),
  }
}

export function mapWatchlistGroup(
  dto: ApiWatchlistGroupWithItemsResponse,
): WatchlistGroup {
  return {
    id: dto.id,
    name: dto.name,
    sortOrder: dto.sort_order,
    isDefault: dto.is_default,
    aiReviewEnabled: dto.ai_review_enabled,
    createdAt: dto.created_at,
    items: (dto.items ?? []).map(mapWatchlistItem),
  }
}
