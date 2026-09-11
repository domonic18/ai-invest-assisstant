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
