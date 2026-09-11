import dayjs from 'dayjs'

/**
 * 单根 K 线涨跌额/幅。change_pct 缺失（sina 渠道大面积空）时按前收盘推算，
 * 与 get_stock_quote 的涨跌口径一致；无前收或收盘为空时返回 null。
 * 入参用结构类型：兼容个股（含 changePct）与指数（仅 OHLC）两类 K 线。
 */
export function deriveBarChange(
  bar: { close: number | null; changePct?: number | null },
  prevClose: number | null | undefined,
): { change: number | null; changePct: number | null } {
  if (bar.changePct != null) {
    return {
      change: prevClose != null && bar.close != null ? bar.close - prevClose : null,
      changePct: bar.changePct,
    }
  }
  if (bar.close == null || prevClose == null || prevClose === 0) {
    return { change: null, changePct: null }
  }
  const change = bar.close - prevClose
  return { change, changePct: (change / prevClose) * 100 }
}

/** 单根 K 线振幅（%）。amplitude 缺失时按 (high-low)/prevClose 推算。 */
export function deriveAmplitude(
  bar: { high: number | null; low: number | null; amplitude?: number | null },
  prevClose: number | null | undefined,
): number | null {
  if (bar.amplitude != null) return bar.amplitude
  if (bar.high == null || bar.low == null || prevClose == null || prevClose === 0) {
    return null
  }
  return ((bar.high - bar.low) / prevClose) * 100
}

/** 成交量格式化为万手（1 手 = 100 股）。 */
export function formatWanShou(volume: number | null | undefined): string {
  if (volume == null) return '-'
  return `${(volume / 100 / 1e4).toFixed(2)}万手`
}

/** 可聚合周 K 的 K 线结构约束（日期为 YYYY-MM-DD，升序）。 */
export interface AggregatableBar {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

/** 该日期所属自然周的周一（YYYY-MM-DD），周分组键。 */
export function weekStartDate(date: string): string {
  const d = dayjs(date)
  return d.subtract((d.day() + 6) % 7, 'day').format('YYYY-MM-DD')
}

/**
 * 日 K 按自然周（周一起）聚合为周 K：开=周首日开、收=周末日收、
 * 高/低取周内极值、量/额求和，date 与其余附加字段取周末日。
 * 入参须按日期升序。
 */
export function aggregateWeeklyBars<T extends AggregatableBar>(bars: T[]): T[] {
  const out: T[] = []
  for (const bar of bars) {
    const head = out[out.length - 1]
    if (head == null || weekStartDate(head.date) !== weekStartDate(bar.date)) {
      out.push({ ...bar })
      continue
    }
    out[out.length - 1] = {
      ...bar,
      open: head.open,
      high: Math.max(head.high, bar.high),
      low: Math.min(head.low, bar.low),
      close: bar.close,
      volume: head.volume + bar.volume,
      amount: head.amount + bar.amount,
    }
  }
  return out
}
