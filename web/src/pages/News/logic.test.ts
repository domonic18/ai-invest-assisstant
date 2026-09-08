import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'

import type { TelegraphItem } from '@ai-invest/shared'

import { countNewMessages, groupByDay, isChannelWired, scoreBand } from './logic'

function item(clsMsgId: number, publishTime: string): TelegraphItem {
  return {
    clsMsgId,
    title: null,
    content: null,
    category: null,
    importance: null,
    shared: null,
    stockCodes: [],
    publishTime,
    sourceUrl: '',
    aiScore: null,
  }
}

describe('scoreBand', () => {
  it('maps aiScore to three bands with null as unscored', () => {
    expect(scoreBand(100)).toBe('high')
    expect(scoreBand(70)).toBe('high')
    expect(scoreBand(69)).toBe('mid')
    expect(scoreBand(40)).toBe('mid')
    expect(scoreBand(39)).toBe('low')
    expect(scoreBand(0)).toBe('low')
    expect(scoreBand(null)).toBe('unscored')
  })
})

describe('groupByDay', () => {
  const now = dayjs('2026-09-08 12:00')

  it('splits descending items into consecutive same-day groups', () => {
    const items = [
      item(3, '2026-09-08T03:00:00Z'),
      item(2, '2026-09-08T01:00:00Z'),
      item(1, '2026-09-07T10:00:00Z'),
    ]
    const groups = groupByDay(items, now)
    expect(groups.map((g) => g.label)).toEqual(['今天', '昨天'])
    expect(groups[0].items.map((i) => i.clsMsgId)).toEqual([3, 2])
    expect(groups[1].items.map((i) => i.clsMsgId)).toEqual([1])
  })

  it('labels older days as M月D日 and returns empty for empty list', () => {
    const groups = groupByDay([item(1, '2026-09-01T02:00:00Z')], now)
    expect(groups[0].label).toBe('9月1日')
    expect(groupByDay([], now)).toEqual([])
  })
})

describe('countNewMessages', () => {
  const items = [item(30, '2026-09-08T04:00:00Z'), item(29, '2026-09-08T03:00:00Z')]

  it('counts items above the seen top id', () => {
    expect(countNewMessages(items, 28)).toBe(2)
    expect(countNewMessages(items, 29)).toBe(1)
    expect(countNewMessages(items, 30)).toBe(0)
  })

  it('returns 0 before baseline is established or list is empty', () => {
    expect(countNewMessages(items, null)).toBe(0)
    expect(countNewMessages([], 28)).toBe(0)
  })
})

describe('isChannelWired', () => {
  it('marks only channels with feed data as wired', () => {
    expect(isChannelWired('cls_telegraph')).toBe(true)
    expect(isChannelWired('sina_news')).toBe(false)
    expect(isChannelWired('eastmoney_research_report')).toBe(false)
  })
})
