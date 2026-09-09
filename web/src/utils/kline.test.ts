import { describe, expect, it } from 'vitest'

import type { StockKlineBar } from '@ai-invest/shared'

import { deriveAmplitude, deriveBarChange, formatWanShou } from './kline'

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
