/** Anomaly analysis (板块/个股异动) API response types (camelCase wire). */

export type AnomalySectorType = 'industry' | 'concept'

export interface ApiSectorAnomalyItem {
  sectorType: string
  sectorCode: string
  sectorName: string
  changePct: number | null
  amount: number | null
  amountRatio: number | null
  upCount: number | null
  downCount: number | null
  anomalyTypes: string[]
  strength: number
  attributionCategory: string | null
  attributionSummary: string | null
}

export interface ApiSectorAnomalyResponse {
  tradeDate: string
  total: number
  items: ApiSectorAnomalyItem[]
}

export interface ApiStockAnomalyItem {
  stockCode: string
  stockName: string
  close: number | null
  changePct: number | null
  turnoverRate: number | null
  volumeRatio: number | null
  ma60: number | null
  isAboveMa60: boolean
  ma60Breakout: boolean
  anomalyTypes: string[]
  strength: number
  attributionCategory: string | null
  attributionSummary: string | null
  isWatchlist: boolean
}

export interface ApiStockAnomalyResponse {
  tradeDate: string
  total: number
  items: ApiStockAnomalyItem[]
}

/** Sector detail (板块详情): THS real kline bridged by sector name. */
export interface ApiSectorKlineBar {
  tradeDate: string
  open: number | null
  high: number | null
  low: number | null
  close: number
  volume: number | null
  amount: number | null
  changePct: number | null
}

export interface ApiSectorFundFlowPoint {
  tradeDate: string
  mainNetInflow: number | null
  superLargeNet: number | null
  largeNet: number | null
  mediumNet: number | null
  smallNet: number | null
}

export interface ApiSectorAnomalyDay {
  tradeDate: string
  anomalyTypes: string[]
  strength: number
  attributionCategory: string | null
  attributionSummary: string | null
}

export interface ApiSectorSnapshot {
  tradeDate: string
  close: number | null
  changePct: number | null
  amount: number | null
  turnoverRate: number | null
  upCount: number | null
  downCount: number | null
  leaderStockName: string | null
}

export interface ApiSectorDetailResponse {
  sectorType: string
  sectorCode: string
  sectorName: string
  bars: ApiSectorKlineBar[]
  fundFlow: ApiSectorFundFlowPoint[]
  anomalyDays: ApiSectorAnomalyDay[]
  snapshot: ApiSectorSnapshot | null
}
