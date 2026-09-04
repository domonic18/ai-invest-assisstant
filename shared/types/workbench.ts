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

/** 自选股概览行的 AI 分析状态：分组未开启 off / 已开启未生成 pending / 已生成 ready。 */
export type WorkbenchAiStatus = 'off' | 'pending' | 'ready'

/** 后端工作台自选股行（snake_case）。 */
export interface ApiWorkbenchWatchlistStock extends ApiWatchlistQuoteItem {
  ai_status: WorkbenchAiStatus
  ai_summary: string | null
}

/** 后端工作台自选股分组（snake_case）。 */
export interface ApiWorkbenchWatchlistGroup {
  id: number
  name: string
  is_default: boolean
  ai_review_enabled: boolean
  items: ApiWorkbenchWatchlistStock[]
}

/** 工作台自选股行：行情 + AI 分析状态。 */
export interface WorkbenchWatchlistStock extends WatchlistQuote {
  aiStatus: WorkbenchAiStatus
  aiSummary: string | null
}

/** 工作台自选股分组。 */
export interface WorkbenchWatchlistGroup {
  id: number
  name: string
  isDefault: boolean
  aiReviewEnabled: boolean
  items: WorkbenchWatchlistStock[]
}

/** 后端板块资金动向卡单行（snake_case，金额单位亿元）。 */
export interface ApiWorkbenchSectorFlowItem {
  sector_name: string
  change_pct: number | null
  main_net_inflow: number | null
  top_stock_name: string | null
}

/** 板块资金动向卡单行（金额单位亿元）。 */
export interface WorkbenchSectorFlowItem {
  sectorName: string
  changePct: number | null
  mainNetInflow: number | null
  topStockName: string | null
}

/** GET /workbench 原始聚合响应（snake_case）。 */
export interface ApiWorkbenchResponse {
  calendar: ApiCalendarEventResponse[]
  review: ApiMarketReviewResponse | null
  telegraph: ApiTelegraphResponse[]
  watchlist_groups: ApiWorkbenchWatchlistGroup[]
  indices: ApiIndexQuoteResponse[]
  stats: ApiMarketStatsResponse | null
  global_indices: ApiGlobalIndexQuoteResponse[]
  sector_flow: ApiWorkbenchSectorFlowItem[]
}

/** 工作台聚合的客户端视图模型。 */
export interface WorkbenchOverview {
  calendar: CalendarEvent[]
  review: MarketReview | null
  telegraph: TelegraphItem[]
  watchlistGroups: WorkbenchWatchlistGroup[]
  indices: IndexQuote[]
  stats: MarketStats | null
  globalIndices: GlobalIndexQuote[]
  sectorFlow: WorkbenchSectorFlowItem[]
}
