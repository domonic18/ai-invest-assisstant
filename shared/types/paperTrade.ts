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
  /** 委托来源：manual 人工 / agent 交易 agent 账户 */
  orderSource?: string
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

/** 模拟盘账户配置行（token 只回掩码，明文不出库）。 */
export interface ApiPaperTradeAccount {
  id: number
  name: string
  counterAccountId: string
  /** 归属交易 Agent；null = 用户账户（agent 专属账户禁止人工下单）。 */
  agentKey: string | null
  isEnabled: boolean
  tokenMasked: string
  lastError?: string | null
  lastSyncedAt?: string | null
  createdAt?: string | null
}

export interface ApiPaperTradeAccountList {
  items: ApiPaperTradeAccount[]
}

/** 管理端账户行（附带归属用户）。 */
export interface ApiPaperTradeAdminAccount extends ApiPaperTradeAccount {
  userId: number
}

export interface ApiPaperTradeAdminAccountList {
  items: ApiPaperTradeAdminAccount[]
}

/** 人工下单请求（限价单必须带价格，柜台校验手数整数倍）。 */
export interface ApiPaperTradePlaceOrderRequest {
  accountId: number
  /** 平台 6 位股票代码；柜台前缀（SHSE./SZSE.）由后端按 stock_basic 主数据解析。 */
  symbol: string
  side: 'buy' | 'sell'
  volume: number
  orderType?: 'limit' | 'market'
  price?: number
}

/** 下单/撤单动作结果。 */
export interface ApiPaperTradeActionResponse {
  success: boolean
  clOrdId: string
  message: string
}

/** 单账户即时同步摘要（下单/撤单后调用）。 */
export interface ApiPaperTradeAccountSyncResponse {
  tradeDate: string
  accountId: number
  orders: number
  executions: number
  nav: number | null
}

/** B/S/T 图表标记单笔成交（当前用户全账户、按标的过滤，tradeDate 升序）。 */
export interface ApiPaperTradeTradeMarker {
  tradeDate: string
  counterCreatedAt?: string | null
  side: 'buy' | 'sell'
  price?: number | null
  volume?: number | null
}

export interface ApiPaperTradeTradeMarkerResponse {
  items: ApiPaperTradeTradeMarker[]
}

/** 账户配置保存请求（新增必填全字段；更新未提供字段不变）。 */
export interface ApiPaperTradeAccountSaveRequest {
  name: string
  token: string
  counterAccountId: string
}
