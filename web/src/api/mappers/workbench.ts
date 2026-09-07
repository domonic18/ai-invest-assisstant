import type {
  ApiCollectorEngineStatus,
  ApiCollectorRunItem,
  ApiCollectorUpcomingItem,
  ApiGlobalIndexQuoteResponse,
  ApiReviewStatus,
  ApiWorkbenchResponse,
  ApiWorkbenchSectorFlowItem,
  CollectorEngineStatus,
  CollectorRunItem,
  CollectorUpcomingItem,
  GlobalIndexQuote,
  ReviewDayStatusItem,
  ReviewStatus,
  WorkbenchSectorFlowItem,
  WorkbenchWatchlistGroup,
  WorkbenchWatchlistStock,
  WorkbenchOverview,
} from '@ai-invest/shared'

import { mapCalendarEvent } from './calendar'
import {
  mapIndexQuote,
  mapMarketReview,
  mapMarketStats,
  mapWatchlistQuote,
} from './market'
import { mapTelegraph } from './telegraph'

export function mapGlobalIndexQuote(
  dto: ApiGlobalIndexQuoteResponse,
): GlobalIndexQuote {
  return {
    indexCode: dto.indexCode,
    indexName: dto.indexName,
    close: dto.close,
    changePct: dto.changePct,
    tradeDate: dto.tradeDate,
  }
}

export function mapWorkbenchWatchlistStock(
  dto: ApiWorkbenchResponse['watchlistGroups'][number]['items'][number],
): WorkbenchWatchlistStock {
  return {
    ...mapWatchlistQuote(dto),
    aiStatus: dto.aiStatus,
    aiSummary: dto.aiSummary,
  }
}

export function mapWorkbenchWatchlistGroup(
  dto: ApiWorkbenchResponse['watchlistGroups'][number],
): WorkbenchWatchlistGroup {
  return {
    id: dto.id,
    name: dto.name,
    isDefault: dto.isDefault,
    aiReviewEnabled: dto.aiReviewEnabled,
    items: dto.items.map(mapWorkbenchWatchlistStock),
  }
}

export function mapSectorFlowItem(
  dto: ApiWorkbenchSectorFlowItem,
): WorkbenchSectorFlowItem {
  return {
    sectorName: dto.sectorName,
    changePct: dto.changePct,
    mainNetInflow: dto.mainNetInflow,
    topStockName: dto.topStockName,
  }
}

export function mapReviewStatus(dto: ApiReviewStatus): ReviewStatus {
  const recentDays: ReviewDayStatusItem[] = (dto.recentDays ?? []).map((day) => ({
    tradeDate: day.tradeDate,
    status: day.status,
  }))
  return {
    status: dto.status,
    tradeDate: dto.tradeDate,
    generatedAt: dto.generatedAt,
    durationSeconds: dto.durationSeconds,
    plannedTime: dto.plannedTime,
    nextRunAt: dto.nextRunAt,
    streakDays: dto.streakDays,
    monthSuccessRate: dto.monthSuccessRate,
    recentDays,
  }
}

export function mapCollectorRunItem(dto: ApiCollectorRunItem): CollectorRunItem {
  return {
    taskName: dto.taskName,
    taskLabel: dto.taskLabel,
    source: dto.source,
    status: dto.status,
    startedAt: dto.startedAt,
    finishedAt: dto.finishedAt,
    durationSeconds: dto.durationSeconds,
    recordsCount: dto.recordsCount,
  }
}

export function mapCollectorUpcomingItem(
  dto: ApiCollectorUpcomingItem,
): CollectorUpcomingItem {
  return {
    runAt: dto.runAt,
    taskName: dto.taskName,
    taskLabel: dto.taskLabel,
    source: dto.source,
  }
}

export function mapCollectorStatus(dto: ApiCollectorEngineStatus): CollectorEngineStatus {
  return {
    isRunning: dto.isRunning,
    running: dto.running ? mapCollectorRunItem(dto.running) : null,
    recentRuns: (dto.recentRuns ?? []).map(mapCollectorRunItem),
    upcoming: (dto.upcoming ?? []).map(mapCollectorUpcomingItem),
  }
}

export function mapWorkbench(dto: ApiWorkbenchResponse): WorkbenchOverview {
  return {
    calendar: dto.calendar.map(mapCalendarEvent),
    review: dto.review ? mapMarketReview(dto.review) : null,
    reviewStatus: dto.reviewStatus ? mapReviewStatus(dto.reviewStatus) : null,
    telegraph: dto.telegraph.map(mapTelegraph),
    watchlistGroups: dto.watchlistGroups.map(mapWorkbenchWatchlistGroup),
    indices: dto.indices.map(mapIndexQuote),
    stats: dto.stats ? mapMarketStats(dto.stats) : null,
    globalIndices: dto.globalIndices.map(mapGlobalIndexQuote),
    sectorFlow: dto.sectorFlow.map(mapSectorFlowItem),
    collectorStatus: dto.collectorStatus
      ? mapCollectorStatus(dto.collectorStatus)
      : null,
  }
}
