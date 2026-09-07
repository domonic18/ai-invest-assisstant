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
    code: dto.stockCode,
    name: dto.stockName,
    industry: dto.industryLevel1 || dto.industryLevel2 || dto.industryLevel3 || '',
    market: normalizeMarket(dto.market),
    fullName: dto.fullName,
    industryLevel1: dto.industryLevel1,
    industryLevel2: dto.industryLevel2,
    industryLevel3: dto.industryLevel3,
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
    date: dto.tradeDate,
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
    prevClose: dto.prevClose,
    change: dto.change,
    changePct: dto.changePct,
    open: dto.open,
    high: dto.high,
    low: dto.low,
    volume: dto.volume,
    amount: dto.amount,
    marketCap: dto.marketCap,
    circulatingMarketCap: dto.circulatingMarketCap,
    updatedAt: dto.updatedAt,
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
      changePct: bar.changePct,
      amplitude: bar.amplitude,
      turnoverRate: bar.turnoverRate,
    })),
  }
}

export function mapIntraday(dto: ApiStockIntradayResponse): StockIntraday {
  return {
    code: dto.code,
    name: dto.name,
    tradeDate: dto.tradeDate,
    prevClose: dto.prevClose,
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
    changePct: dto.changePct,
    mainNetInflow: dto.mainNetInflow,
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
    date: dto.tradeDate,
    time: dto.matchTime,
    price: Number(dto.price),
    volume: Number(dto.volume),
    bidPrices: dto.bidPrices,
    bidVolumes: dto.bidVolumes,
    askPrices: dto.askPrices,
    askVolumes: dto.askVolumes,
  }
}

export function mapWatchlistItem(dto: ApiWatchlistItemResponse): WatchlistItem {
  return {
    id: String(dto.id),
    code: dto.stockCode,
    tags: dto.tags || [],
    groupId: dto.groupId,
    createdAt: dto.createdAt,
  }
}

export function mapStockAiAnalysis(dto: ApiStockAiAnalysisResponse): StockAiAnalysis {
  return {
    stockCode: dto.stockCode,
    stockName: dto.stockName,
    tradeDate: dto.tradeDate,
    model: dto.model,
    generatedAt: dto.generatedAt,
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
    sortOrder: dto.sortOrder,
    isDefault: dto.isDefault,
    aiReviewEnabled: dto.aiReviewEnabled,
    createdAt: dto.createdAt,
    items: (dto.items ?? []).map(mapWatchlistItem),
  }
}
