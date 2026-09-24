/**
 * 模拟盘 wire 类型（与 backend/app/schemas/paper_trade.py camelCase 对齐）。
 *
 * 金额一律 number（后端 wire 层 float，DB 层 NUMERIC）；柜台原值透传字段
 * （side/orderType/status 等）的中文映射见 shared/constants/paperTrade.ts。
 */

export interface ApiPaperTradeCash {
  nav?: number | null
  available?: number | null
  balance?: number | null
  cumInout?: number | null
  lastInout?: number | null
}

export interface ApiPaperTradePosition {
  symbol: string
  stockCode: string
  side?: number | null
  volume?: number | null
  availableVolume?: number | null
  avgPrice?: number | null
  lastPrice?: number | null
  marketValue?: number | null
  profit?: number | null
  profitRate?: number | null
}

export interface ApiPaperTradeOrder {
  clOrdId: string
  tradeDate: string
  symbol: string
  stockCode: string
  side: number
  orderType: number
  positionEffect: number
  price: number
  volume: number
  status: number
  ordRejReason?: number | null
  ordRejReasonDetail?: string | null
  counterCreatedAt?: string | null
  counterUpdatedAt?: string | null
}

export interface ApiPaperTradeExecution {
  execId: string
  clOrdId: string
  tradeDate: string
  symbol: string
  side?: number | null
  execType?: number | null
  price?: number | null
  volume?: number | null
  turnover?: number | null
  commission?: number | null
  counterCreatedAt?: string | null
}

export interface ApiPaperTradeOverview {
  /** false = 模拟盘功能未配置（前端展示引导卡而非报错） */
  enabled: boolean
  cash?: ApiPaperTradeCash | null
  positions: ApiPaperTradePosition[]
  unfinishedOrders: ApiPaperTradeOrder[]
}

export interface ApiPaperTradeNavPoint {
  tradeDate: string
  nav?: number | null
  available?: number | null
}

export interface ApiPaperTradeNavResponse {
  items: ApiPaperTradeNavPoint[]
}

export interface ApiPaperTradeOrderPage {
  total: number
  page: number
  pageSize: number
  tradeDate: string
  items: ApiPaperTradeOrder[]
}

export interface ApiPaperTradeExecutionPage {
  total: number
  page: number
  pageSize: number
  tradeDate: string
  items: ApiPaperTradeExecution[]
}
