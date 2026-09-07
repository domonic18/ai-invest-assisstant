import { ENDPOINTS } from '@ai-invest/shared'
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

import { apiClient } from './client'
import { mapCalendarEvent, mapTelegraph } from './mappers'
import {
  mapIndexQuote,
  mapMarketReview,
  mapMarketStats,
  mapWatchlistQuote,
} from './market'

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

export function mapWatchlistStock(
  dto: ApiWorkbenchResponse['watchlistGroups'][number]['items'][number],
): WorkbenchWatchlistStock {
  return {
    ...mapWatchlistQuote(dto),
    aiStatus: dto.aiStatus,
    aiSummary: dto.aiSummary,
  }
}

export function mapWatchlistGroup(
  dto: ApiWorkbenchResponse['watchlistGroups'][number],
): WorkbenchWatchlistGroup {
  return {
    id: dto.id,
    name: dto.name,
    isDefault: dto.isDefault,
    aiReviewEnabled: dto.aiReviewEnabled,
    items: dto.items.map(mapWatchlistStock),
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
    watchlistGroups: dto.watchlistGroups.map(mapWatchlistGroup),
    indices: dto.indices.map(mapIndexQuote),
    stats: dto.stats ? mapMarketStats(dto.stats) : null,
    globalIndices: dto.globalIndices.map(mapGlobalIndexQuote),
    sectorFlow: dto.sectorFlow.map(mapSectorFlowItem),
    collectorStatus: dto.collectorStatus
      ? mapCollectorStatus(dto.collectorStatus)
      : null,
  }
}

export async function fetchWorkbench(): Promise<WorkbenchOverview> {
  const response = await apiClient.get<ApiWorkbenchResponse>(
    ENDPOINTS.workbench.base,
  )
  return mapWorkbench(response.data)
}
