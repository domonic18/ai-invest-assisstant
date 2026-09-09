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

/** 后端工作台自选股行。 */
export interface ApiWorkbenchWatchlistStock extends ApiWatchlistQuoteItem {
  aiStatus: WorkbenchAiStatus
  aiSummary: string | null
}

/** 后端工作台自选股分组。 */
export interface ApiWorkbenchWatchlistGroup {
  id: number
  name: string
  isDefault: boolean
  aiReviewEnabled: boolean
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

/** 后端板块资金动向卡单行（金额单位亿元）。 */
export interface ApiWorkbenchSectorFlowItem {
  sectorName: string
  changePct: number | null
  mainNetInflow: number | null
  topStockName: string | null
}

/** 板块资金动向卡单行（金额单位亿元）。 */
export interface WorkbenchSectorFlowItem {
  sectorName: string
  changePct: number | null
  mainNetInflow: number | null
  topStockName: string | null
}

/** 单个交易日的复盘生成结果。 */
export type ReviewDayStatus = 'success' | 'failed' | 'pending'

/** 后端近段交易日复盘结果行。 */
export interface ApiReviewDayStatus {
  tradeDate: string
  status: ReviewDayStatus
}

/** 视图模型：近段交易日复盘结果行。 */
export interface ReviewDayStatusItem {
  tradeDate: string
  status: ReviewDayStatus
}

/** 复盘整体状态：done 已生成 / pending 待生成 / failed 生成失败。 */
export type ReviewStatusState = 'done' | 'pending' | 'failed'

/** 后端复盘状态卡数据。 */
export interface ApiReviewStatus {
  status: ReviewStatusState
  tradeDate: string
  generatedAt: string | null
  durationSeconds: number | null
  plannedTime: string | null
  nextRunAt: string | null
  streakDays: number
  monthSuccessRate: number | null
  recentDays: ApiReviewDayStatus[]
}

/** 复盘状态卡数据。 */
export interface ReviewStatus {
  status: ReviewStatusState
  tradeDate: string
  generatedAt: string | null
  durationSeconds: number | null
  plannedTime: string | null
  nextRunAt: string | null
  streakDays: number
  monthSuccessRate: number | null
  recentDays: ReviewDayStatusItem[]
}

/** 后端采集引擎运行记录。 */
export interface ApiCollectorRunItem {
  taskName: string
  taskLabel: string
  source: string | null
  status: string
  startedAt: string | null
  finishedAt: string | null
  durationSeconds: number | null
  recordsCount: number | null
}

/** 采集引擎运行记录。 */
export interface CollectorRunItem {
  taskName: string
  taskLabel: string
  source: string | null
  status: string
  startedAt: string | null
  finishedAt: string | null
  durationSeconds: number | null
  recordsCount: number | null
}

/** 后端采集引擎计划运行项。 */
export interface ApiCollectorUpcomingItem {
  runAt: string
  taskName: string
  taskLabel: string
  source: string | null
}

/** 采集引擎计划运行项。 */
export interface CollectorUpcomingItem {
  runAt: string
  taskName: string
  taskLabel: string
  source: string | null
}

/** 后端采集引擎状态。 */
export interface ApiCollectorEngineStatus {
  isRunning: boolean
  running: ApiCollectorRunItem | null
  recentRuns: ApiCollectorRunItem[]
  upcoming: ApiCollectorUpcomingItem[]
}

/** 采集引擎状态。 */
export interface CollectorEngineStatus {
  isRunning: boolean
  running: CollectorRunItem | null
  recentRuns: CollectorRunItem[]
  upcoming: CollectorUpcomingItem[]
}

/** GET /workbench 原始聚合响应（camelCase wire）。 */
export interface ApiWorkbenchResponse {
  calendar: ApiCalendarEventResponse[]
  review: ApiMarketReviewResponse | null
  reviewStatus: ApiReviewStatus | null
  telegraph: ApiTelegraphResponse[]
  watchlistGroups: ApiWorkbenchWatchlistGroup[]
  indices: ApiIndexQuoteResponse[]
  stats: ApiMarketStatsResponse | null
  globalIndices: ApiGlobalIndexQuoteResponse[]
  sectorFlow: ApiWorkbenchSectorFlowItem[]
  collectorStatus: ApiCollectorEngineStatus | null
}

/** 工作台聚合的客户端视图模型。 */
export interface WorkbenchOverview {
  calendar: CalendarEvent[]
  review: MarketReview | null
  reviewStatus: ReviewStatus | null
  telegraph: TelegraphItem[]
  watchlistGroups: WorkbenchWatchlistGroup[]
  indices: IndexQuote[]
  stats: MarketStats | null
  globalIndices: GlobalIndexQuote[]
  sectorFlow: WorkbenchSectorFlowItem[]
  collectorStatus: CollectorEngineStatus | null
}
