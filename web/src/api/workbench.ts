import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiGlobalIndexQuoteResponse,
  ApiWorkbenchResponse,
  GlobalIndexQuote,
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

export function mapWorkbench(dto: ApiWorkbenchResponse): WorkbenchOverview {
  return {
    calendar: dto.calendar.map(mapCalendarEvent),
    review: dto.review ? mapMarketReview(dto.review) : null,
    telegraph: dto.telegraph.map(mapTelegraph),
    watchlistGroups: dto.watchlist_groups.map(mapWatchlistGroup),
    indices: dto.indices.map(mapIndexQuote),
    stats: dto.stats ? mapMarketStats(dto.stats) : null,
    globalIndices: dto.global_indices.map(mapGlobalIndexQuote),
  }
}

export async function fetchWorkbench(): Promise<WorkbenchOverview> {
  const response = await apiClient.get<ApiWorkbenchResponse>(
    ENDPOINTS.workbench.base,
  )
  return mapWorkbench(response.data)
}
