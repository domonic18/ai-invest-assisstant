import type {
  ApiCollectTaskResult,
  ApiIndexIntradayResponse,
  ApiIndexKlineResponse,
  ApiIndexQuoteResponse,
  ApiLimitUpItem,
  ApiLimitUpResponse,
  ApiMarketReviewResponse,
  ApiMarketStatsResponse,
  ApiSectorOverviewResponse,
  ApiWatchlistQuoteItem,
  CollectTaskResult,
  IndexIntraday,
  IndexKline,
  IndexKlinePeriod,
  IndexQuote,
  LimitUpData,
  LimitUpStock,
  MarketReview,
  MarketStats,
  SectorOverview,
  WatchlistQuote,
} from '@ai-invest/shared'

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

export function mapIndexIntraday(dto: ApiIndexIntradayResponse): IndexIntraday {
  return {
    code: dto.code,
    name: dto.name,
    tradeDate: dto.tradeDate,
    prevClose: dto.prevClose,
    points: dto.points,
  }
}

export function mapIndexKline(dto: ApiIndexKlineResponse): IndexKline {
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

export function mapLimitUpStock(dto: ApiLimitUpItem): LimitUpStock {
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

export function mapLimitUpData(dto: ApiLimitUpResponse): LimitUpData {
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

export function mapSectorOverview(dto: ApiSectorOverviewResponse): SectorOverview {
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

export function mapCollectTaskResult(dto: ApiCollectTaskResult): CollectTaskResult {
  return {
    task: dto.task,
    status: dto.status,
    itemsCollected: dto.itemsCollected,
    errors: dto.errors,
  }
}
