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
    indexCode: dto.index_code,
    indexName: dto.index_name,
    close: dto.close,
    changePct: dto.change_pct,
    tradeDate: dto.trade_date,
  }
}

export function mapWatchlistStock(dto: {
  code: string
  name: string | null
  price: number | null
  change_pct: number | null
  amount: number | null
  tags: string[]
  updated_at: string | null
  trend?: number[]
  ai_status: WorkbenchWatchlistStock['aiStatus']
  ai_summary: string | null
}): WorkbenchWatchlistStock {
  return {
    ...mapWatchlistQuote(dto),
    aiStatus: dto.ai_status,
    aiSummary: dto.ai_summary,
  }
}

export function mapWatchlistGroup(
  dto: ApiWorkbenchResponse['watchlist_groups'][number],
): WorkbenchWatchlistGroup {
  return {
    id: dto.id,
    name: dto.name,
    isDefault: dto.is_default,
    aiReviewEnabled: dto.ai_review_enabled,
    items: dto.items.map(mapWatchlistStock),
  }
}

export function mapSectorFlowItem(
  dto: ApiWorkbenchSectorFlowItem,
): WorkbenchSectorFlowItem {
  return {
    sectorName: dto.sector_name,
    changePct: dto.change_pct,
    mainNetInflow: dto.main_net_inflow,
    topStockName: dto.top_stock_name,
  }
}

export function mapReviewStatus(dto: ApiReviewStatus): ReviewStatus {
  const recentDays: ReviewDayStatusItem[] = (dto.recent_days ?? []).map((day) => ({
    tradeDate: day.trade_date,
    status: day.status,
  }))
  return {
    status: dto.status,
    tradeDate: dto.trade_date,
    generatedAt: dto.generated_at,
    durationSeconds: dto.duration_seconds,
    plannedTime: dto.planned_time,
    nextRunAt: dto.next_run_at,
    streakDays: dto.streak_days,
    monthSuccessRate: dto.month_success_rate,
    recentDays,
  }
}

export function mapCollectorRunItem(dto: ApiCollectorRunItem): CollectorRunItem {
  return {
    taskName: dto.task_name,
    taskLabel: dto.task_label,
    source: dto.source,
    status: dto.status,
    startedAt: dto.started_at,
    finishedAt: dto.finished_at,
    durationSeconds: dto.duration_seconds,
    recordsCount: dto.records_count,
  }
}

export function mapCollectorUpcomingItem(
  dto: ApiCollectorUpcomingItem,
): CollectorUpcomingItem {
  return {
    runAt: dto.run_at,
    taskName: dto.task_name,
    taskLabel: dto.task_label,
    source: dto.source,
  }
}

export function mapCollectorStatus(dto: ApiCollectorEngineStatus): CollectorEngineStatus {
  return {
    isRunning: dto.is_running,
    running: dto.running ? mapCollectorRunItem(dto.running) : null,
    recentRuns: (dto.recent_runs ?? []).map(mapCollectorRunItem),
    upcoming: (dto.upcoming ?? []).map(mapCollectorUpcomingItem),
  }
}

export function mapWorkbench(dto: ApiWorkbenchResponse): WorkbenchOverview {
  return {
    calendar: dto.calendar.map(mapCalendarEvent),
    review: dto.review ? mapMarketReview(dto.review) : null,
    reviewStatus: dto.review_status ? mapReviewStatus(dto.review_status) : null,
    telegraph: dto.telegraph.map(mapTelegraph),
    watchlistGroups: dto.watchlist_groups.map(mapWatchlistGroup),
    indices: dto.indices.map(mapIndexQuote),
    stats: dto.stats ? mapMarketStats(dto.stats) : null,
    globalIndices: dto.global_indices.map(mapGlobalIndexQuote),
    sectorFlow: dto.sector_flow.map(mapSectorFlowItem),
    collectorStatus: dto.collector_status
      ? mapCollectorStatus(dto.collector_status)
      : null,
  }
}

export async function fetchWorkbench(): Promise<WorkbenchOverview> {
  const response = await apiClient.get<ApiWorkbenchResponse>(
    ENDPOINTS.workbench.base,
  )
  return mapWorkbench(response.data)
}
