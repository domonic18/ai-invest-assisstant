import { describe, expect, it } from 'vitest'

import {
  extractPageResult,
  extractPageResultFromMessages,
} from './runtimeUtils'

function toolMessage(event: Record<string, unknown>) {
  return { type: 'tool', content: { __event__: event } }
}

describe('extractPageResultFromMessages', () => {
  it('extracts industry_chain analysis event', () => {
    const result = extractPageResultFromMessages([
      toolMessage({
        type: 'industry_chain.analysis.complete',
        industry: '半导体',
        version_id: 123,
        version_no: 5,
      }),
    ])
    expect(result).toEqual({
      type: 'industry_chain.analysis.complete',
      industry: '半导体',
      versionId: 123,
      versionNo: 5,
      createdAt: undefined,
    })
  })

  it('extracts stock_daily_analysis event', () => {
    const result = extractPageResultFromMessages([
      toolMessage({
        type: 'stock_daily_analysis.complete',
        stock_code: '600519',
        trade_date: '2026-09-04',
      }),
    ])
    expect(result).toEqual({
      type: 'stock_daily_analysis.complete',
      stockCode: '600519',
      tradeDate: '2026-09-04',
    })
  })

  it('extracts event from JSON-string serialized tool content', () => {
    const result = extractPageResultFromMessages([
      {
        type: 'tool',
        content: JSON.stringify({
          stock_code: '600519',
          __event__: { type: 'stock_daily_analysis.complete', stock_code: '600519', trade_date: '2026-09-04' },
        }),
      },
    ])
    expect(result).toEqual({
      type: 'stock_daily_analysis.complete',
      stockCode: '600519',
      tradeDate: '2026-09-04',
    })
  })

  it('returns null when no page event present', () => {
    const result = extractPageResultFromMessages([
      { type: 'tool', content: 'plain text' },
      toolMessage({ type: 'unrelated.event' }),
    ])
    expect(result).toBeNull()
  })
})

describe('extractPageResult', () => {
  it('scans node updates for stock event', () => {
    const updates = {
      agent: { messages: [toolMessage({
        type: 'stock_daily_analysis.complete',
        stock_code: '000001',
        trade_date: '2026-09-03',
      })] },
    }
    expect(extractPageResult(updates)).toEqual({
      type: 'stock_daily_analysis.complete',
      stockCode: '000001',
      tradeDate: '2026-09-03',
    })
  })
})
