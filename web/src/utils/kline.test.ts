import { describe, expect, it } from 'vitest'

import type { StockKlineBar } from '@ai-invest/shared'

import {
  aggregateWeeklyBars,
  deriveAmplitude,
  deriveBarChange,
  formatWanShou,
  weekStartDate,
} from './kline'

const bar = (over: Partial<StockKlineBar>): StockKlineBar => ({
  date: '2026-09-04',
  open: 100,
  high: 110,
  low: 98,
  close: 105,
  volume: 8420000,
  amount: 2.67e9,
  changePct: null,
  amplitude: null,
  turnoverRate: null,
  ...over,
})

describe('deriveBarChange', () => {
  it('derives change from prevClose when changePct missing', () => {
    const { change, changePct } = deriveBarChange(bar({ close: 105 }), 100)
    expect(change).toBeCloseTo(5)
    expect(changePct).toBeCloseTo(5)
  })

  it('prefers stored changePct', () => {
    const { changePct } = deriveBarChange(bar({ close: 105, changePct: 3.5 }), 100)
    expect(changePct).toBeCloseTo(3.5)
  })

  it('returns nulls without prevClose', () => {
    const { change, changePct } = deriveBarChange(bar({ close: 105 }), null)
    expect(change).toBeNull()
    expect(changePct).toBeNull()
  })
})

describe('deriveAmplitude', () => {
  it('derives amplitude from high/low/prevClose', () => {
    expect(deriveAmplitude(bar({ high: 110, low: 98 }), 100)).toBeCloseTo(12)
  })

  it('prefers stored amplitude', () => {
    expect(deriveAmplitude(bar({ high: 110, low: 98, amplitude: 6.02 }), 100)).toBeCloseTo(6.02)
  })

  it('returns null without prevClose', () => {
    expect(deriveAmplitude(bar({ high: 110, low: 98 }), null)).toBeNull()
  })
})

describe('formatWanShou', () => {
  it('formats volume in 万手 (1手=100股)', () => {
    expect(formatWanShou(8420000)).toBe('8.42万手')
  })

  it('handles null', () => {
    expect(formatWanShou(null)).toBe('-')
  })
})

describe('weekStartDate', () => {
  it('maps mid-week dates to Monday', () => {
    // 2026-09-07 周一 ～ 2026-09-13 周日 同属一周
    expect(weekStartDate('2026-09-07')).toBe('2026-09-07')
    expect(weekStartDate('2026-09-09')).toBe('2026-09-07')
    expect(weekStartDate('2026-09-13')).toBe('2026-09-07')
  })

  it('maps weekend back to Monday of same week', () => {
    expect(weekStartDate('2026-09-12')).toBe('2026-09-07')
    expect(weekStartDate('2026-09-14')).toBe('2026-09-14')
  })
})

describe('aggregateWeeklyBars', () => {
  it('aggregates same-week dailies into one bar (last date, extremes, sums)', () => {
    const weekly = aggregateWeeklyBars([
      bar({ date: '2026-09-07', open: 100, high: 102, low: 99, close: 101, volume: 10, amount: 1 }),
      bar({ date: '2026-09-08', open: 101, high: 108, low: 100, close: 106, volume: 20, amount: 2 }),
      bar({ date: '2026-09-09', open: 106, high: 107, low: 95, close: 98, volume: 30, amount: 3 }),
    ])
    expect(weekly).toHaveLength(1)
    expect(weekly[0]).toMatchObject({
      date: '2026-09-09',
      open: 100,
      close: 98,
      high: 108,
      low: 95,
      volume: 60,
      amount: 6,
    })
  })

  it('starts a new bar when the week changes', () => {
    const weekly = aggregateWeeklyBars([
      bar({ date: '2026-09-11', close: 100, volume: 10, amount: 1 }),
      bar({ date: '2026-09-14', close: 105, volume: 20, amount: 2 }),
    ])
    expect(weekly.map((b) => b.date)).toEqual(['2026-09-11', '2026-09-14'])
    expect(weekly[1]).toMatchObject({ open: 100, close: 105 })
  })

  it('keeps preserve of other fields from the last bar of each week', () => {
    const weekly = aggregateWeeklyBars([
      bar({ date: '2026-09-08', changePct: 1.5 }),
      bar({ date: '2026-09-09', changePct: -2.0 }),
    ])
    expect(weekly[0].changePct).toBeCloseTo(-2.0)
  })

  it('handles empty input', () => {
    expect(aggregateWeeklyBars([])).toEqual([])
  })
})
