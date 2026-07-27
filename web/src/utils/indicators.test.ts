import { describe, expect, it } from 'vitest'

import { calculateKDJ, calculateMACD } from './indicators'

describe('calculateMACD', () => {
  it('returns nulls until enough data', () => {
    const closes = Array.from({ length: 26 }, (_, i) => i + 1)
    const result = calculateMACD(closes)
    expect(result.dif[0]).toBeNull()
    expect(result.dea[25]).not.toBeNull()
  })

  it('produces zero-ish histogram when DIF equals DEA', () => {
    const closes = Array.from({ length: 40 }, () => 100)
    const result = calculateMACD(closes)
    expect(result.dif[39]).toBeCloseTo(0, 5)
    expect(result.dea[39]).toBeCloseTo(0, 5)
    expect(result.macd[39]).toBeCloseTo(0, 5)
  })
})

describe('calculateKDJ', () => {
  it('returns nulls for the first n-1 bars', () => {
    const values = Array.from({ length: 12 }, (_, i) => i + 10)
    const result = calculateKDJ(values, values, values, 9)
    expect(result.k[7]).toBeNull()
    expect(result.k[8]).not.toBeNull()
  })

  it('produces J = 3K - 2D', () => {
    const highs = Array.from({ length: 12 }, (_, i) => i + 20)
    const lows = Array.from({ length: 12 }, (_, i) => i + 10)
    const closes = Array.from({ length: 12 }, (_, i) => i + 15)
    const result = calculateKDJ(highs, lows, closes, 9)
    const lastK = result.k[11] as number
    const lastD = result.d[11] as number
    const lastJ = result.j[11] as number
    expect(lastJ).toBeCloseTo(3 * lastK - 2 * lastD, 5)
  })
})
