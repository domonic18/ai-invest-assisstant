import { describe, expect, it } from 'vitest'

import type { StockKlineBar } from '@ai-invest/shared'

import { buildKlineOption, prepareKlineData } from './klineOption'

const bar = (
  date: string,
  close: number,
  open = close - 1,
  high = close + 2,
  low = close - 2,
): StockKlineBar => ({
  date,
  open,
  high,
  low,
  close,
  volume: 1000,
  amount: 1e8,
  changePct: null,
  amplitude: null,
  turnoverRate: null,
})

const INDICATORS = { volume: true, ma: false, macd: false, kdj: false }

function candleMarkLineData(
  option: ReturnType<typeof buildKlineOption>,
): unknown[] {
  const candle = (option.series as { name: string; markLine?: { data: unknown[] } }[]).find(
    (s) => s.name === 'K线',
  )
  expect(candle).toBeDefined()
  return candle?.markLine?.data ?? []
}

describe('buildKlineOption markers', () => {
  const bars = [bar('2026-09-01', 10), bar('2026-09-02', 11), bar('2026-09-03', 12)]
  const data = prepareKlineData({ bars }, [])

  it('merges anomaly date lines with the last-price tag line', () => {
    const option = buildKlineOption(data, INDICATORS, 400, [
      { date: '2026-09-02', label: '异动' },
    ])
    const markData = candleMarkLineData(option)
    expect(
      markData.some((d) => (d as { xAxis?: string }).xAxis === '2026-09-02'),
    ).toBe(true)
    expect(markData.some((d) => (d as { yAxis?: number }).yAxis === 12)).toBe(true)
  })

  it('drops markers whose date misses the axis', () => {
    const option = buildKlineOption(data, INDICATORS, 400, [
      { date: '1999-01-01' },
    ])
    const markData = candleMarkLineData(option)
    expect(markData).toHaveLength(1)
    expect(markData[0]).toMatchObject({ yAxis: 12 })
  })

  it('keeps only the last-price line without markers', () => {
    const option = buildKlineOption(data, INDICATORS, 400)
    expect(candleMarkLineData(option)).toHaveLength(1)
  })
})
