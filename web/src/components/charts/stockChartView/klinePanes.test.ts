import { describe, expect, it } from 'vitest'

import type { StockKlineBar } from '@ai-invest/shared'

import { fmt } from '@/components/charts/chartShared'
import { fallHex, riseHex } from '@/utils/formatters'

import { prepareKlineData } from './klineData'
import {
  computePaneLayout,
  subPaneLegendId,
  subPaneLegendTitle,
} from './klinePanes'

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

describe('computePaneLayout', () => {
  it('defaults topReserve to 8', () => {
    const panes = computePaneLayout(400, 2)
    expect(panes[0].top).toBe(8)
  })

  it('honors the MA legend topReserve override', () => {
    const panes = computePaneLayout(400, 2, 34)
    expect(panes[0].top).toBe(34)
  })
})

describe('subPaneLegendTitle', () => {
  // MACD 需要 validCount >= slow(26) 才产出非空 dif，取 40 根上升收盘
  const bars = Array.from({ length: 40 }, (_, i) =>
    bar(`2026-07-${String((i % 28) + 1).padStart(2, '0')}`, 10 + i),
  )
  const data = prepareKlineData({ bars }, [])
  const up = riseHex()
  const down = fallHex()

  it('anchors macd legend values to the given idx, not the series tail', () => {
    const idx = 30
    const mid = subPaneLegendTitle('macd', data, idx, up, down)
    expect(mid.text).toContain(`DIF: ${fmt(data.macd.dif[idx])}`)
    expect(mid.text).toContain(`DEA: ${fmt(data.macd.dea[idx])}`)
    const tail = subPaneLegendTitle('macd', data, data.dates.length - 1, up, down)
    expect(mid.text).not.toBe(tail.text)
  })

  it('renders static text for volume legend', () => {
    expect(subPaneLegendTitle('volume', data, 0, up, down).text).toBe('VOL(万手)')
  })

  it('stabilizes legend ids per pane key', () => {
    expect(subPaneLegendId('macd')).toBe('legend-macd')
    expect(subPaneLegendId('kdj')).toBe('legend-kdj')
  })
})
