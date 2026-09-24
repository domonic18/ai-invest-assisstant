/** B/S/T 标记纯转换测试：期望值由显式偏移 fixture 推导，与 runner 时区无关。 */

import { describe, expect, it } from 'vitest'

import type { ApiPaperTradeTradeMarker } from '@ai-invest/shared'

import {
  toIntradayTradeMarks,
  toKlineTradeMarks,
} from './tradeMarkers'

const m = (over: Partial<ApiPaperTradeTradeMarker>): ApiPaperTradeTradeMarker => ({
  tradeDate: '2026-09-21',
  counterCreatedAt: '2026-09-21T01:30:00Z',
  side: 'buy',
  price: 10,
  volume: 100,
  ...over,
})

describe('toKlineTradeMarks', () => {
  it('仅买入聚合为 B，价格为成交量加权均价', () => {
    const marks = toKlineTradeMarks([
      m({ price: 10, volume: 100 }),
      m({ price: 11, volume: 300 }),
    ])
    expect(marks).toEqual([{ date: '2026-09-21', label: 'B', price: 10.75 }])
  })

  it('仅卖出为 S', () => {
    expect(toKlineTradeMarks([m({ side: 'sell' })])).toEqual([
      { date: '2026-09-21', label: 'S', price: 10 },
    ])
  })

  it('同日双向为 T', () => {
    const marks = toKlineTradeMarks([
      m({ side: 'buy', price: 10, volume: 100 }),
      m({ side: 'sell', price: 20, volume: 100 }),
    ])
    expect(marks).toEqual([{ date: '2026-09-21', label: 'T', price: 15 }])
  })

  it('跨日各自成桶且按日期升序', () => {
    const marks = toKlineTradeMarks([
      m({ tradeDate: '2026-09-22' }),
      m({ tradeDate: '2026-09-21' }),
    ])
    expect(marks.map((k) => k.date)).toEqual(['2026-09-21', '2026-09-22'])
  })

  it('缺失价格或数量的回报跳过', () => {
    expect(toKlineTradeMarks([m({ price: null }), m({ volume: null })])).toEqual([])
  })
})

describe('toIntradayTradeMarks', () => {
  it('UTC 回报转北京墙钟 HH:mm', () => {
    expect(toIntradayTradeMarks([m({ counterCreatedAt: '2026-09-21T01:30:00Z' })])).toEqual([
      { time: '09:30', side: 'buy', price: 10 },
    ])
    expect(toIntradayTradeMarks([m({ counterCreatedAt: '2026-09-21T05:14:00Z' })])).toEqual([
      { time: '13:14', side: 'buy', price: 10 },
    ])
  })

  it('缺时刻或价格的回报丢弃', () => {
    expect(toIntradayTradeMarks([m({ counterCreatedAt: null })])).toEqual([])
    expect(toIntradayTradeMarks([m({ price: null })])).toEqual([])
  })
})
