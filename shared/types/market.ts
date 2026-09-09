/** Market overview (每日复盘) API response types (camelCase wire). */
export interface ApiIndexQuoteResponse {
  code: string
  name: string
  price: number
  change: number
  changePct: number
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
  tradeDate: string
  prevClose: number
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

export interface ApiLimitUpItem {
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

export interface ApiLimitUpGroup {
  name: string
  count: number
  changePct: number | null
  mainNetInflow: number | null
  reason: string | null
  items: ApiLimitUpItem[]
}

export interface ApiLimitUpResponse {
  tradeDate: string
  total: number
  firstBoard: number
  continuous: number
  maxBoards: number | null
  ladder: ApiLimitUpItem[]
  items: ApiLimitUpItem[]
  groups: ApiLimitUpGroup[]
  aiGenerated: boolean
}

export interface ApiLimitUpIntradayResponse {
  tradeDate: string
  series: Record<string, number[]>
}

export interface ApiSectorHeatItem {
  sectorName: string
  changePct: number | null
}

export interface ApiSectorFlowItem {
  sectorName: string
  mainNetInflow: number | null
  topStockName: string | null
}

export interface ApiLeadingSectorItem {
  sectorName: string
  changePct: number | null
  limitUpCount: number
  mainNetInflow: number | null
  topStockNames: string[]
}

export interface ApiSectorOverviewResponse {
  tradeDate: string
  heatmap: ApiSectorHeatItem[]
  topInflow: ApiSectorFlowItem[]
  topOutflow: ApiSectorFlowItem[]
  leading: ApiLeadingSectorItem[]
}

export interface ApiWatchlistQuoteItem {
  code: string
  name: string | null
  price: number | null
  changePct: number | null
  amount: number | null
  tags: string[]
  updatedAt: string | null
  trend?: number[]
}

export interface ApiMarketReviewSection {
  key: string
  title: string
  content: string
}

export interface ApiMarketReviewResponse {
  tradeDate: string
  sections: ApiMarketReviewSection[]
  model: string | null
  generatedAt: string
  cached: boolean
  edited: boolean
}

export interface ApiMarketCollectRequest {
  tradeDate: string
}

export interface ApiCollectTaskResult {
  task: string
  status: string
  itemsCollected: number
  errors: string[]
}

export interface ApiMarketReviewUpdateRequest {
  tradeDate: string
  sectionKey: string
  content: string
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
  trend: number[]
}

export interface ApiGlobalIndexQuoteResponse {
  indexCode: string
  indexName: string
  close: number | null
  changePct: number | null
  tradeDate: string | null
  trend: number[]
}

export interface GlobalIndexQuote {
  indexCode: string
  indexName: string
  close: number | null
  changePct: number | null
  tradeDate: string | null
  trend: number[]
}

export interface GlobalIndexHistoryPoint {
  tradeDate: string
  close: number
}

export interface FedWatchMeeting {
  meetingDate: string
  probHike: number
  probHold: number
  probCut: number
  likelyRangeLow: number
  likelyRangeHigh: number
}

export interface FedWatchResponse {
  asOf: string
  dataAsAt: string
  currentRangeLow: number
  currentRangeHigh: number
  meetings: FedWatchMeeting[]
}

export interface SectorQuoteItem {
  sectorType: string
  sectorCode: string
  sectorName: string
  close: number | null
  changePct: number | null
  amount: number | null
  turnoverRate: number | null
  upCount: number | null
  downCount: number | null
  leaderStockName: string | null
}

export interface SectorQuoteResponse {
  tradeDate: string
  items: SectorQuoteItem[]
}

export interface MarketReviewSection {
  key: string
  title: string
  content: string
}

export interface MarketReview {
  tradeDate: string
  sections: MarketReviewSection[]
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
