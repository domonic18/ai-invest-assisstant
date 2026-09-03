import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiGlobalIndexQuoteResponse,
  ApiWorkbenchResponse,
  GlobalIndexQuote,
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

export function mapWorkbench(dto: ApiWorkbenchResponse): WorkbenchOverview {
  return {
    calendar: dto.calendar.map(mapCalendarEvent),
    review: dto.review ? mapMarketReview(dto.review) : null,
    telegraph: dto.telegraph.map(mapTelegraph),
    watchlist: dto.watchlist.map(mapWatchlistQuote),
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
