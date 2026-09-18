import { describe, expect, it } from 'vitest'
import dayjs from 'dayjs'

import type { ApiCollectorHealthTaskItem } from '@ai-invest/shared'

import { domainGroupStats, lastSuccessText } from './constants'

describe('lastSuccessText', () => {
  // 用无时区偏移的本地 wall-clock 字符串，断言与 runner 时区无关
  const now = dayjs('2026-09-13T15:00:00')

  it('returns 从未成功 for null', () => {
    expect(lastSuccessText(null, now)).toBe('从未成功')
  })

  it('formats today as 今天 HH:mm', () => {
    expect(lastSuccessText('2026-09-13T09:25:00', now)).toBe('今天 09:25')
  })

  it('formats yesterday as 昨天 HH:mm', () => {
    expect(lastSuccessText('2026-09-12T21:40:00', now)).toBe('昨天 21:40')
  })

  it('formats within 30 days as N 天前', () => {
    expect(lastSuccessText('2026-08-31T18:00:00', now)).toBe('13 天前')
  })

  it('falls back to MM-DD at or beyond 30 days', () => {
    expect(lastSuccessText('2026-08-10T18:00:00', now)).toBe('08-10')
  })

  it('生产形状（+08:00 偏移 ISO）与等价 naive 输入产出一致', () => {
    // 本地渲染约定：偏移输入不二次转换，行为与本地等价值完全一致
    const offset = '2026-09-13T09:25:00+08:00'
    const naive = dayjs(offset).format('YYYY-MM-DDTHH:mm:ss')
    expect(lastSuccessText(offset, now)).toBe(lastSuccessText(naive, now))
  })

  it('偏移输入跨 30 天回退 MM-DD 与等价 naive 一致', () => {
    const offset = '2026-08-10T18:00:00+08:00'
    const naive = dayjs(offset).format('YYYY-MM-DDTHH:mm:ss')
    expect(lastSuccessText(offset, now)).toBe(lastSuccessText(naive, now))
  })
})

function task(overrides: Partial<ApiCollectorHealthTaskItem>): ApiCollectorHealthTaskItem {
  return {
    taskType: 't',
    source: 'sina',
    status: 'healthy',
    role: 'primary',
    domain: 'kline',
    successRate24h: null,
    successRate7d: null,
    consecutiveFailures: 0,
    windowsWithoutSuccess: 0,
    lastSuccessAt: null,
    lastErrorSummary: null,
    lastErrorCause: null,
    reasons: [],
    isHighFrequency: false,
    lastRecordsCount: null,
    lastRecordsDate: null,
    stateChangedAt: '2026-09-13T00:00:00',
    checkedAt: '2026-09-13T00:00:00',
    schedule: null,
    isActive: true,
    ...overrides,
  }
}

describe('domainGroupStats', () => {
  it('returns empty for no tasks', () => {
    expect(domainGroupStats([])).toEqual([])
  })

  it('counts total and abnormal per domain keeping first-seen order', () => {
    const stats = domainGroupStats([
      task({ taskType: 'a', domain: 'kline', status: 'healthy' }),
      task({ taskType: 'b', domain: 'quote', status: 'critical' }),
      task({ taskType: 'c', domain: 'kline', status: 'degraded' }),
      task({ taskType: 'd', domain: 'kline', status: 'silent' }),
      task({ taskType: 'e', domain: 'quote', status: 'unconfigured' }),
    ])
    expect(stats).toEqual([
      { domain: 'kline', total: 3, abnormal: 2 },
      { domain: 'quote', total: 2, abnormal: 1 },
    ])
  })

  it('treats paused and unconfigured as non-abnormal', () => {
    const stats = domainGroupStats([
      task({ taskType: 'a', domain: 'pool', status: 'paused' }),
      task({ taskType: 'b', domain: 'pool', status: 'unconfigured' }),
    ])
    expect(stats).toEqual([{ domain: 'pool', total: 2, abnormal: 0 }])
  })
})
