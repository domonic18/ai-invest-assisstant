import { describe, expect, it } from 'vitest'

import { PAGE_EVENT_DEFINITIONS, parsePageEvent } from './pageEvents'

describe('parsePageEvent', () => {
  it('parses chain event with action label', () => {
    const parsed = parsePageEvent({
      type: 'industry_chain.analysis_complete',
      industry: '半导体',
      version_id: 123,
      version_no: 5,
    })
    expect(parsed).not.toBeNull()
    expect(parsed?.result).toEqual({
      type: 'industry_chain.analysis_complete',
      industry: '半导体',
      versionId: 123,
      versionNo: 5,
      createdAt: undefined,
    })
    expect(parsed?.actionLabel).toBeTruthy()
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
  })

  it('returns null for unregistered or malformed events', () => {
    expect(parsePageEvent({ type: 'unknown.event' })).toBeNull()
    expect(parsePageEvent('not-an-object')).toBeNull()
    expect(parsePageEvent(null)).toBeNull()
  })

  it('event types are unique', () => {
    const types = PAGE_EVENT_DEFINITIONS.map((d) => d.eventType)
    expect(new Set(types).size).toBe(types.length)
  })
})
