/** A 股模拟交易纯规则：交易时段、涨跌停价、最大可买可卖（无副作用，供下单卡与委托页复用）。 */

import type { Dayjs } from 'dayjs'

import { bjNow, toBeijing } from '@/utils/beijing'

export type MarketSession = 'open' | 'break' | 'pre' | 'closed'

interface SessionSpan {
  label: string
  tone: 'success' | 'warning' | 'default'
  hint: string
}

export const SESSION_LABEL: Record<MarketSession, SessionSpan> = {
  open: { label: '交易中', tone: 'success', hint: '委托即时报送柜台' },
  break: {
    label: '午间休市',
    tone: 'warning',
    hint: '委托将被柜台接收，13:00 开盘后报送',
  },
  pre: {
    label: '未开盘',
    tone: 'warning',
    hint: '委托将被柜台接收，开盘后报送',
  },
  closed: {
    label: '已收盘',
    tone: 'default',
    hint: '委托将被柜台接收，下一交易日开盘后报送',
  },
}

/** 北京墙钟交易时段：周一至周五 9:30-11:30 / 13:00-15:00（节假日无法前端识别，以柜台为准）。 */
export function marketSession(now: Dayjs = bjNow()): MarketSession {
  const bj = toBeijing(now)
  const day = bj.day()
  if (day === 0 || day === 6) return 'closed'
  const minutes = bj.hour() * 60 + bj.minute()
  if (minutes >= 570 && minutes < 690) return 'open' // 9:30-11:30
  if (minutes >= 780 && minutes < 900) return 'open' // 13:00-15:00
  if (minutes >= 690 && minutes < 780) return 'break' // 11:30-13:00
  if (minutes < 570) return 'pre'
  return 'closed'
}

export function isMarketOpen(now: Dayjs = bjNow()): boolean {
  return marketSession(now) === 'open'
}

/** 涨跌停幅度（%）：ST ±5，创业板(30)/科创板(68) ±20，其余主板 ±10。 */
export function priceLimitPct(name: string | undefined, code: string): number {
  if (name && name.toUpperCase().includes('ST')) return 5
  if (code.startsWith('30') || code.startsWith('68')) return 20
  return 10
}

/** 按前收盘推算涨跌停价，四舍五入到分。 */
export function limitPrices(prevClose: number, limitPct: number): {
  limitUp: number
  limitDown: number
} {
  const factor = limitPct / 100
  return {
    limitUp: Math.round(prevClose * (1 + factor) * 100) / 100,
    limitDown: Math.round(prevClose * (1 - factor) * 100) / 100,
  }
}

/** 最大可买：可用资金按限价折算，向下取整到手（100 股）。 */
export function maxBuyVolume(cashAvailable: number, price: number): number {
  if (price <= 0 || cashAvailable <= 0) return 0
  return Math.floor(cashAvailable / price / 100) * 100
}

/** 最大可卖：可用持仓（T+1 已由柜台字段 available 体现），向下取整到手。 */
export function maxSellVolume(availableVolume: number): number {
  if (availableVolume <= 0) return 0
  return Math.floor(availableVolume / 100) * 100
}
