/**
 * 模拟盘柜台枚举的中文映射（掘金 OrderStatus / OrderSide / OrderType 原值）。
 *
 * 状态字典来源：myquant 仿真柜台（gmtrade SDK 同源枚举）；未知原值回退
 * 「原值」字样，柜台演进不致前端渲染空白。
 */

export const PAPER_TRADE_ORDER_STATUS: Record<number, string> = {
  0: '未知',
  1: '已报',
  2: '部成',
  3: '已成',
  4: '部撤',
  5: '已撤',
  6: '待撤',
  8: '已拒',
}

export const PAPER_TRADE_SIDE: Record<number, string> = {
  1: '买入',
  2: '卖出',
}

export const PAPER_TRADE_ORDER_TYPE: Record<number, string> = {
  1: '限价',
  2: '市价',
}

export const PAPER_TRADE_ORDER_SOURCE: Record<string, string> = {
  manual: '人工',
  agent: 'Agent',
}

export function paperTradeOrderStatus(status?: number | null): string {
  if (status == null) return '-'
  return PAPER_TRADE_ORDER_STATUS[status] ?? `状态${status}`
}

export function paperTradeSide(side?: number | null): string {
  if (side == null) return '-'
  return PAPER_TRADE_SIDE[side] ?? `${side}`
}

export function paperTradeOrderType(orderType?: number | null): string {
  if (orderType == null) return '-'
  return PAPER_TRADE_ORDER_TYPE[orderType] ?? `${orderType}`
}

export function paperTradeOrderSource(source?: string | null): string {
  if (!source) return '-'
  return PAPER_TRADE_ORDER_SOURCE[source] ?? source
}
