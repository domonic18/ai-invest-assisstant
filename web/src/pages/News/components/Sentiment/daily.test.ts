/** 账号卡按日时序纯逻辑：多账号合并与总量统计。 */
import { describe, expect, it } from 'vitest'

import type { ApiSocialAccountCard } from '@ai-invest/shared'

import { mergeAccountDaily, sumStance } from './daily'

function account(daily: ApiSocialAccountCard['daily']): ApiSocialAccountCard {
  return {
    id: 1,
    alias: '财经大V',
    category: 'finance_kol',
    lastPostAt: null,
    latestStance: null,
    latestConfidence: null,
    latestSummary: null,
    latestCoverUrl: null,
    bullishCount: 0,
    bearishCount: 0,
    neutralCount: 0,
    daily,
  }
}

describe('mergeAccountDaily', () => {
  it('sums per-day stance counts across accounts and sorts ascending', () => {
    const merged = mergeAccountDaily([
      account([
        { date: '2026-09-15', bullish: 2, bearish: 1, neutral: 0 },
        { date: '2026-09-16', bullish: 0, bearish: 2, neutral: 1 },
      ]),
      account([{ date: '2026-09-16', bullish: 3, bearish: 0, neutral: 0 }]),
    ])
    expect(merged).toEqual([
      { date: '2026-09-15', bullish: 2, bearish: 1, neutral: 0 },
      { date: '2026-09-16', bullish: 3, bearish: 2, neutral: 1 },
    ])
  })

  it('returns empty for accounts without daily rows', () => {
    expect(mergeAccountDaily([account([]), account([])])).toEqual([])
  })
})

describe('sumStance', () => {
  it('totals stance counts across rows', () => {
    expect(
      sumStance([
        { date: '2026-09-15', bullish: 2, bearish: 1, neutral: 3 },
        { date: '2026-09-16', bullish: 1, bearish: 0, neutral: 1 },
      ]),
    ).toEqual({ bullish: 3, bearish: 1, neutral: 4 })
  })
})
