export interface Stock {
  code: string
  name: string
  industry: string
  market: 'SH' | 'SZ' | 'BJ'
  fullName?: string | null
  industryLevel1?: string | null
  industryLevel2?: string | null
  industryLevel3?: string | null
}

export interface StockQuote {
  code: string
  name: string
  price: number | null
  prevClose: number | null
  change: number | null
  changePct: number | null
  open: number | null
  high: number | null
  low: number | null
  volume: number | null
  amount: number | null
  marketCap: number | null
  circulatingMarketCap: number | null
  updatedAt: string | null
}

export interface StockKlineBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
  changePct: number | null
  amplitude: number | null
  turnoverRate: number | null
}

export interface StockKline {
  code: string
  name: string
  period: string
  bars: StockKlineBar[]
}

export interface StockIntradayPoint {
  time: string
  price: number
  volume: number
  amount: number
}

export interface StockIntraday {
  code: string
  name: string
  tradeDate: string
  prevClose: number
  points: StockIntradayPoint[]
}

export interface StockSector {
  name: string
  type: 'industry' | 'concept'
  changePct: number | null
  mainNetInflow: number | null
}

export interface KlineData {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

export interface AuctionData {
  date: string
  time: string
  price: number
  volume: number
  bidPrices: number[]
  bidVolumes: number[]
  askPrices: number[]
  askVolumes: number[]
}

export interface FundFlowData {
  code: string
  date: string
  mainNetInflow: number
  superLargeNet: number
  largeNet: number
  mediumNet: number
  smallNet: number
}

export interface WatchlistItem {
  id: string
  code: string
  name?: string
  tags: string[]
  groupId: number
  price?: number
  changePercent?: number
  createdAt: string
}

export interface WatchlistGroup {
  id: number
  name: string
  sortOrder: number
  isDefault: boolean
  aiReviewEnabled: boolean
  createdAt: string
  items: WatchlistItem[]
}

export interface StockAiAnalysisSection {
  key: string
  title: string
  content: string
}

export interface StockAiAnalysis {
  stockCode: string
  stockName: string
  tradeDate: string
  model: string | null
  generatedAt: string
  cached: boolean
  sections: StockAiAnalysisSection[]
}
