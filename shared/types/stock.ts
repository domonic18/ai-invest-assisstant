export interface Stock {
  code: string
  name: string
  industry: string
  market: 'SH' | 'SZ' | 'BJ'
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
  price?: number
  changePercent?: number
  createdAt: string
}
