/** 模拟盘成交 → 图表 B/S/T 标记的纯转换：K 线按日聚合（B=仅买/S=仅卖/T=同日双向），分时逐笔落点。 */

import dayjs from 'dayjs'

import type { ApiPaperTradeTradeMarker } from '@ai-invest/shared'

import { toBeijing } from '@/utils/beijing'

export type TradeMarkerItems = ApiPaperTradeTradeMarker[]

export interface KlineTradeMark {
  date: string
  label: 'B' | 'S' | 'T'
  price: number
}

export interface IntradayTradeMark {
  /** 北京墙钟 HH:mm，与分时 points[].time 同轴。 */
  time: string
  side: 'buy' | 'sell'
  price: number
}

/** 按日聚合为 B/S/T，价格取当日成交量加权均价。 */
export function toKlineTradeMarks(items: TradeMarkerItems): KlineTradeMark[] {
  const byDate = new Map<string, { buyVol: number; sellVol: number; notional: number; vol: number }>()
  for (const item of items) {
    if (item.price == null || item.volume == null || item.volume <= 0) continue
    const bucket = byDate.get(item.tradeDate) ?? { buyVol: 0, sellVol: 0, notional: 0, vol: 0 }
    if (item.side === 'buy') bucket.buyVol += item.volume
    else bucket.sellVol += item.volume
    bucket.notional += Number(item.price) * item.volume
    bucket.vol += item.volume
    byDate.set(item.tradeDate, bucket)
  }
  return [...byDate.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([date, b]) => ({
      date,
      label: b.buyVol > 0 && b.sellVol > 0 ? 'T' : b.buyVol > 0 ? 'B' : 'S',
      price: b.vol > 0 ? b.notional / b.vol : 0,
    }))
}

/** 回报时刻转北京墙钟 HH:mm；缺时刻或无效时间的回报丢弃。 */
export function toIntradayTradeMarks(items: TradeMarkerItems): IntradayTradeMark[] {
  return items
    .filter((i) => i.price != null)
    .map((i) => {
      const bj = i.counterCreatedAt ? toBeijing(dayjs(i.counterCreatedAt)) : null
      return bj && bj.isValid()
        ? { time: bj.format('HH:mm'), side: i.side, price: Number(i.price) }
        : null
    })
    .filter((m): m is IntradayTradeMark => m != null)
}
