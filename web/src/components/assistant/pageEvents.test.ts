import { describe, expect, it } from 'vitest'

import { PAGE_EVENT_DEFINITIONS, parsePageEvent } from './pageEvents'

describe('parsePageEvent', () => {
  it('parses chain event with action label and result page path', () => {
    const parsed = parsePageEvent({
      type: 'industry_chain.analysis.complete',
      industry: '半导体',
      version_id: 123,
      version_no: 5,
    })
    expect(parsed).not.toBeNull()
    expect(parsed?.result).toEqual({
      type: 'industry_chain.analysis.complete',
      industry: '半导体',
      versionId: 123,
      versionNo: 5,
      createdAt: undefined,
    })
    expect(parsed?.actionLabel).toBeTruthy()
    expect(parsed?.path).toBe(`/chain/${encodeURIComponent('半导体')}`)
  })

  it('parses stock daily analysis event', () => {
    const parsed = parsePageEvent({
      type: 'stock_daily_analysis.complete',
      stock_code: '600519',
      trade_date: '2026-09-04',
    })
    expect(parsed?.result).toEqual({
      type: 'stock_daily_analysis.complete',
      stockCode: '600519',
      tradeDate: '2026-09-04',
    })
    expect(parsed?.path).toBe('/stock/600519')
  })

  it('parses review and limit-up events to the review page', () => {
    const review = parsePageEvent({
      type: 'market_daily_review.complete',
      trade_date: '2026-09-05',
    })
    expect(review?.path).toBe('/review')
    const attribution = parsePageEvent({
      type: 'limit_up_attribution.complete',
      trade_date: '2026-09-05',
    })
    expect(attribution?.path).toBe('/review')
  })

  it('returns null for unregistered or malformed events', () => {
    expect(parsePageEvent({ type: 'unknown.event' })).toBeNull()
    expect(parsePageEvent('not-an-object')).toBeNull()
    expect(parsePageEvent(null)).toBeNull()
  })

  it('parses kline drawing events to the target chart page', () => {
    const stock = parsePageEvent({
      type: 'kline_drawing.complete',
      target_type: 'stock',
      target_code: '600519',
      period: 'daily',
      count: 5,
    })
    expect(stock?.path).toBe('/stock/600519')
    expect(stock?.actionLabel).toBe('查看 AI 画线')

    const index = parsePageEvent({
      type: 'kline_drawing.complete',
      target_type: 'index',
      target_code: 'sh000001',
      period: 'daily',
      count: 3,
    })
    expect(index?.path).toBe('/index/sh000001')

    const sector = parsePageEvent({
      type: 'kline_drawing.complete',
      target_type: 'sector',
      target_code: '881125',
      period: 'daily',
      count: 2,
      sector_type: 'concept',
    })
    expect(sector?.path).toBe('/sector/concept/881125')
  })

  it('parses paper trading order events to the trading agent page', () => {
    const parsed = parsePageEvent({
      type: 'paper_trading.complete',
      action: 'order',
      cl_ord_id: 'abc123',
      symbol: '600000',
      side: 'buy',
      volume: 100,
    })
    expect(parsed?.result).toEqual({
      type: 'paper_trading.complete',
      action: 'order',
      clOrdId: 'abc123',
      symbol: '600000',
      side: 'buy',
      volume: 100,
    })
    expect(parsed?.path).toBe('/trading-agent')
  })

  it('event types are unique and every definition declares a path', () => {
    const types = PAGE_EVENT_DEFINITIONS.map((d) => d.eventType)
    expect(new Set(types).size).toBe(types.length)
    for (const definition of PAGE_EVENT_DEFINITIONS) {
      expect(definition.actionLabel).toBeTruthy()
      expect(typeof definition.path).toBe('function')
    }
  })
})
