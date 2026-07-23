/** Market overview (每日复盘) API response types (snake_case, 与后端一致). */
export interface ApiIndexQuoteResponse {
  code: string
  name: string
  price: number
  change: number
  change_pct: number
  amount: number | null
  trend: number[]
}

export interface ApiIndexIntradayPoint {
  time: string
  price: number
  volume: number
  amount: number
}

export interface ApiIndexIntradayResponse {
  code: string
  name: string
  trade_date: string
  prev_close: number
  points: ApiIndexIntradayPoint[]
}

export type IndexKlinePeriod =
  | 'daily'
  | 'weekly'
  | 'monthly'
  | 'quarterly'
  | 'yearly'

export interface ApiIndexKlineBar {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  amount: number | null
}

export interface ApiIndexKlineResponse {
  code: string
  name: string
  period: string
  bars: ApiIndexKlineBar[]
}

export interface ApiMarketStatsResponse {
  trade_date: string
  amount: number | null
  prev_amount: number | null
  amount_change: number | null
  amount_change_pct: number | null
  up_count: number | null
  down_count: number | null
  flat_count: number | null
  limit_up_count: number
  limit_down_count: number
  broken_limit_count: number | null
  emotion_score: number | null
  emotion_label: string | null
  limit_up_ratio: number | null
  continuous_rate: number | null
  broken_rate: number | null
}

export interface ApiLimitUpItem {
  stock_code: string
  stock_name: string | null
  change_pct: number | null
  latest_price: number | null
  sealed_amount: number | null
  first_seal_time: string | null
  last_seal_time: string | null
  broken_limit_count: number | null
  limit_status: string | null
  consecutive_boards: number | null
  industry: string | null
  seal_type: string | null
  themes: string[]
}

export interface ApiLimitUpGroup {
  name: string
  count: number
  change_pct: number | null
  main_net_inflow: number | null
  reason: string | null
  items: ApiLimitUpItem[]
}

export interface ApiLimitUpResponse {
  trade_date: string
  total: number
  first_board: number
  continuous: number
  max_boards: number | null
  ladder: ApiLimitUpItem[]
  items: ApiLimitUpItem[]
  groups: ApiLimitUpGroup[]
  ai_generated: boolean
}

export interface ApiLimitUpIntradayResponse {
  trade_date: string
  series: Record<string, number[]>
}

export interface ApiSectorHeatItem {
  sector_name: string
  change_pct: number | null
}

export interface ApiSectorFlowItem {
  sector_name: string
  main_net_inflow: number | null
  top_stock_name: string | null
}

export interface ApiLeadingSectorItem {
  sector_name: string
  change_pct: number | null
  limit_up_count: number
  main_net_inflow: number | null
  top_stock_names: string[]
}

export interface ApiSectorOverviewResponse {
  trade_date: string
  heatmap: ApiSectorHeatItem[]
  top_inflow: ApiSectorFlowItem[]
  top_outflow: ApiSectorFlowItem[]
  leading: ApiLeadingSectorItem[]
}

export interface ApiWatchlistQuoteItem {
  code: string
  name: string | null
  price: number | null
  change_pct: number | null
  amount: number | null
  tags: string[]
  updated_at: string | null
}

export interface ApiMarketReviewResponse {
  trade_date: string
  overview: string
  emotion_analysis: string
  capital_analysis: string
  risk_advice: string
  model: string | null
  generated_at: string
  cached: boolean
  edited: boolean
}

export interface ApiMarketReviewGenerateRequest {
  trade_date?: string
  regenerate?: boolean
}

export interface ApiMarketCollectRequest {
  trade_date: string
}

export interface ApiCollectTaskResult {
  task: string
  status: string
  items_collected: number
  errors: string[]
}

export interface ApiMarketReviewUpdateRequest {
  trade_date: string
  overview: string
  emotion_analysis: string
  capital_analysis: string
  risk_advice: string
}

/** Domain types (camelCase) for frontend consumption. */
export interface IndexQuote {
  code: string
  name: string
  price: number
  change: number
  changePct: number
  amount: number | null
  trend: number[]
}

export interface IndexIntradayPoint {
  time: string
  price: number
  volume: number
  amount: number
}

export interface IndexIntraday {
  code: string
  name: string
  tradeDate: string
  prevClose: number
  points: IndexIntradayPoint[]
}

export interface IndexKlineBar {
  date: string
  open: number | null
  high: number | null
  low: number | null
  close: number | null
  volume: number | null
  amount: number | null
}

export interface IndexKline {
  code: string
  name: string
  period: IndexKlinePeriod
  bars: IndexKlineBar[]
}

export interface MarketStats {
  tradeDate: string
  amount: number | null
  prevAmount: number | null
  amountChange: number | null
  amountChangePct: number | null
  upCount: number | null
  downCount: number | null
  flatCount: number | null
  limitUpCount: number
  limitDownCount: number
  brokenLimitCount: number | null
  emotionScore: number | null
  emotionLabel: string | null
  limitUpRatio: number | null
  continuousRate: number | null
  brokenRate: number | null
}

export interface LimitUpStock {
  stockCode: string
  stockName: string | null
  changePct: number | null
  latestPrice: number | null
  sealedAmount: number | null
  firstSealTime: string | null
  lastSealTime: string | null
  brokenLimitCount: number | null
  limitStatus: string | null
  consecutiveBoards: number | null
  industry: string | null
  sealType: string | null
  themes: string[]
}

export interface LimitUpGroup {
  name: string
  count: number
  changePct: number | null
  mainNetInflow: number | null
  reason: string | null
  items: LimitUpStock[]
}

export interface LimitUpData {
  tradeDate: string
  total: number
  firstBoard: number
  continuous: number
  maxBoards: number | null
  ladder: LimitUpStock[]
  items: LimitUpStock[]
  groups: LimitUpGroup[]
  aiGenerated: boolean
}

export interface LimitUpIntraday {
  tradeDate: string
  series: Record<string, number[]>
}

export interface SectorHeatCell {
  sectorName: string
  changePct: number | null
}

export interface SectorFlowEntry {
  sectorName: string
  mainNetInflow: number | null
  topStockName: string | null
}

export interface LeadingSector {
  sectorName: string
  changePct: number | null
  limitUpCount: number
  mainNetInflow: number | null
  topStockNames: string[]
}

export interface SectorOverview {
  tradeDate: string
  heatmap: SectorHeatCell[]
  topInflow: SectorFlowEntry[]
  topOutflow: SectorFlowEntry[]
  leading: LeadingSector[]
}

export interface WatchlistQuote {
  code: string
  name: string | null
  price: number | null
  changePct: number | null
  amount: number | null
  tags: string[]
  updatedAt: string | null
}

export interface MarketReview {
  tradeDate: string
  overview: string
  emotionAnalysis: string
  capitalAnalysis: string
  riskAdvice: string
  model: string | null
  generatedAt: string
  cached: boolean
  edited: boolean
}

export interface CollectTaskResult {
  task: string
  status: string
  itemsCollected: number
  errors: string[]
}
