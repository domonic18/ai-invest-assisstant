import type { StockKlineBar } from '@ai-invest/shared'

/**
 * 单根 K 线涨跌额/幅。change_pct 缺失（sina 渠道大面积空）时按前收盘推算，
 * 与 get_stock_quote 的涨跌口径一致；无前收时返回 null。
 */
export function deriveBarChange(
  bar: Pick<StockKlineBar, 'close' | 'changePct'>,
  prevClose: number | null | undefined,
): { change: number | null; changePct: number | null } {
  if (bar.changePct != null) {
    return {
      change: prevClose != null ? bar.close - prevClose : null,
      changePct: bar.changePct,
    }
  }
  if (prevClose == null || prevClose === 0) return { change: null, changePct: null }
  const change = bar.close - prevClose
  return { change, changePct: (change / prevClose) * 100 }
}

/** 单根 K 线振幅（%）。amplitude 缺失时按 (high-low)/prevClose 推算。 */
export function deriveAmplitude(
  bar: Pick<StockKlineBar, 'high' | 'low' | 'amplitude'>,
  prevClose: number | null | undefined,
): number | null {
  if (bar.amplitude != null) return bar.amplitude
  if (prevClose == null || prevClose === 0) return null
  return ((bar.high - bar.low) / prevClose) * 100
}

/** 成交量格式化为万手（1 手 = 100 股）。 */
export function formatWanShou(volume: number | null | undefined): string {
  if (volume == null) return '-'
  return `${(volume / 100 / 1e4).toFixed(2)}万手`
}
