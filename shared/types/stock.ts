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

export interface WatchlistItem {
  code: string
  name: string
  price: number
  changePercent: number
}
