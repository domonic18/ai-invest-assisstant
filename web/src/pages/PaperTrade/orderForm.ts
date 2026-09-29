/**
 * 下单卡纯逻辑（类型 + 校验 + 小工具），与 TradingPanel 的 JSX 分离以便单测。
 * 校验函数返回 Promise 以直接适配 antd Form rules 的 validator 签名。
 */
import type { ApiPaperTradePosition } from '@ai-invest/shared'

/** 持仓行/外部入口回填下单卡的载荷（symbol 用 6 位代码）。 */
export interface OrderPrefill {
  symbol: string
  side: 'buy' | 'sell'
  price?: number
  volume?: number
}

/** 提取平台规范的 6 位股票代码（行情查询与下单提交共用）；
 * 接受裸代码或粘贴的带前缀代码（SZSE.000037）。柜台前缀由后端按主数据解析。 */
export function stockCode(raw: string | undefined): string {
  const match = raw?.trim().toUpperCase().match(/(\d{6})/)
  return match ? match[1] : ''
}

export function findPosition(
  positions: ApiPaperTradePosition[] | undefined,
  code: string,
): ApiPaperTradePosition | undefined {
  if (!code) return undefined
  return positions?.find(
    (p) => p.stockCode === code || p.symbol.endsWith(code),
  )
}

/** 交易时段 Tag 的 tone → antd color 映射。 */
export const SESSION_TAG_COLOR: Record<string, string> = {
  success: 'green',
  warning: 'orange',
  default: 'default',
}

/** 快捷仓位档位：按最大可买/可卖取比例，再整手取整。 */
export const QUICK_RATIOS: { label: string; ratio: number }[] = [
  { label: '1/4仓', ratio: 0.25 },
  { label: '半仓', ratio: 0.5 },
  { label: '3/4仓', ratio: 0.75 },
  { label: '全仓', ratio: 1 },
]

/** 涨跌停价（limitPrices 产物）。 */
export interface PriceLimits {
  limitUp: number
  limitDown: number
}

/** 限价校验：必填 + 不得越过涨跌停（越界将被柜台拒单）。 */
export function validateLimitPrice(
  value: number | undefined,
  limits: PriceLimits | null,
): Promise<void> {
  if (value == null) return Promise.reject(new Error('限价单必须带价格'))
  if (limits) {
    if (value > limits.limitUp)
      return Promise.reject(
        new Error(`超过涨停价 ${limits.limitUp.toFixed(2)}，将被柜台拒单`),
      )
    if (value < limits.limitDown)
      return Promise.reject(
        new Error(`低于跌停价 ${limits.limitDown.toFixed(2)}，将被柜台拒单`),
      )
  }
  return Promise.resolve()
}

/** 数量校验：整手 + 卖方持仓/最大可卖 + 买方资金上限。 */
export function validateOrderVolume(
  value: number | undefined,
  opts: {
    side: 'buy' | 'sell'
    position: ApiPaperTradePosition | undefined
    maxBuy: number | null
    maxSell: number | null
  },
): Promise<void> {
  if (value == null) return Promise.reject(new Error('输入数量'))
  if (value % 100 !== 0)
    return Promise.reject(new Error('数量须为 100 股整数倍'))
  if (opts.side === 'sell') {
    if (!opts.position || (opts.position.availableVolume ?? 0) <= 0)
      return Promise.reject(new Error('该标的无可卖持仓（T+1 未可用亦不可卖）'))
    if (opts.maxSell != null && value > opts.maxSell)
      return Promise.reject(new Error(`超过最大可卖 ${opts.maxSell} 股`))
  } else if (opts.maxBuy != null && value > opts.maxBuy) {
    return Promise.reject(
      new Error(`资金不足，最大可买 ${opts.maxBuy} 股`),
    )
  }
  return Promise.resolve()
}
