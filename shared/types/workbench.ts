import type {
  ApiCalendarEventResponse,
  CalendarEvent,
} from './calendar'
import type {
  ApiGlobalIndexQuoteResponse,
  ApiIndexQuoteResponse,
  ApiMarketReviewResponse,
  ApiMarketStatsResponse,
  ApiWatchlistQuoteItem,
  GlobalIndexQuote,
  IndexQuote,
  MarketReview,
  MarketStats,
  WatchlistQuote,
} from './market'
import type { ApiTelegraphResponse, TelegraphItem } from './telegraph'

/** GET /workbench 原始聚合响应（snake_case）。 */
export interface ApiWorkbenchResponse {
  calendar: ApiCalendarEventResponse[]
  review: ApiMarketReviewResponse | null
  telegraph: ApiTelegraphResponse[]
  watchlist: ApiWatchlistQuoteItem[]
  indices: ApiIndexQuoteResponse[]
  stats: ApiMarketStatsResponse | null
  global_indices: ApiGlobalIndexQuoteResponse[]
}

/** 工作台聚合的客户端视图模型。 */
export interface WorkbenchOverview {
  calendar: CalendarEvent[]
  review: MarketReview | null
  telegraph: TelegraphItem[]
  watchlist: WatchlistQuote[]
  indices: IndexQuote[]
  stats: MarketStats | null
  globalIndices: GlobalIndexQuote[]
}
