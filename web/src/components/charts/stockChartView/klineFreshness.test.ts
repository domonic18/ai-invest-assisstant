import { describe, expect, it } from 'vitest'

import { isKlineBehind, isPublishPending, shanghaiNow } from './klineFreshness'

describe('isKlineBehind', () => {
  it('最后一根 bar 早于最近交易日时判定落后', () => {
    expect(isKlineBehind('2026-09-10', '2026-09-11')).toBe(true)
  })

  it('齐平或缺少任一日期时不判定落后', () => {
    expect(isKlineBehind('2026-09-11', '2026-09-11')).toBe(false)
    expect(isKlineBehind(undefined, '2026-09-11')).toBe(false)
    expect(isKlineBehind('2026-09-11', undefined)).toBe(false)
  })
})

describe('isPublishPending', () => {
  const cnMorning = new Date('2026-09-11T10:00:00+08:00')
  const cnEvening = new Date('2026-09-11T18:00:00+08:00')

  it('期望日为今天且未过 17:00 发布窗口时抑制补采', () => {
    expect(isPublishPending('2026-09-11', cnMorning)).toBe(true)
    expect(isPublishPending('2026-09-11', cnEvening)).toBe(false)
  })

  it('期望日为过去的完成交易日时不抑制', () => {
    expect(isPublishPending('2026-09-10', cnMorning)).toBe(false)
  })

  it('缺少期望日时不抑制', () => {
    expect(isPublishPending(undefined, cnMorning)).toBe(false)
  })
})

describe('shanghaiNow', () => {
  it('按 Asia/Shanghai 归一日与分钟数（跨时区换算）', () => {
    // 纽约 2026-09-10 16:30（UTC-4）= 上海 2026-09-11 04:30
    const parts = shanghaiNow(new Date('2026-09-10T16:30:00-04:00'))
    expect(parts).toEqual({ date: '2026-09-11', minutes: 4 * 60 + 30 })
  })
})
