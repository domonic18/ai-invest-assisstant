import { describe, expect, it } from 'vitest'
import dayjs from 'dayjs'

import {
  cronZh,
  formatNextRunLabel,
  isHighFreq,
  nextRuns,
  parseCron,
  runsOnDate,
} from './cron'

// 统一用显式北京墙钟起点（2026-09-17 周四 10:00 CST），不依赖运行环境时区
const FROM = dayjs('2026-09-17T10:00:00+08:00')

describe('parseCron', () => {
  it('expands wildcard to 60 minutes (high freq)', () => {
    const p = parseCron('* * * * *')
    expect(p).not.toBeNull()
    expect(p!.minutes).toHaveLength(60)
    expect(p!.minuteStep).toBe(1)
    expect(isHighFreq(p!)).toBe(true)
  })

  it('expands step field with minuteStep', () => {
    const p = parseCron('*/5 9-15 * * 1-5')
    expect(p!.minutes).toEqual([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
    expect(p!.minuteStep).toBe(5)
    expect(p!.hours).toEqual([9, 10, 11, 12, 13, 14, 15])
    expect(p!.dows).toEqual([1, 2, 3, 4, 5])
    expect(isHighFreq(p!)).toBe(true)
  })

  it('expands range with step in hours (a-b/n)', () => {
    const p = parseCron('*/10 9-11/2 * * *')
    expect(p!.hours).toEqual([9, 11])
    expect(p!.minutes).toEqual([0, 10, 20, 30, 40, 50])
  })

  it('parses lists and keeps dom/month as null when wildcard', () => {
    const p = parseCron('0 8,18 * * *')
    expect(p!.minutes).toEqual([0])
    expect(p!.hours).toEqual([8, 18])
    expect(p!.doms).toBeNull()
    expect(p!.months).toBeNull()
    expect(p!.dows).toBeNull()
    expect(isHighFreq(p!)).toBe(false)
  })

  it('normalizes dow 7 to 0 and parses dom/month', () => {
    const p = parseCron('0 3 1 * 7')
    expect(p!.doms).toEqual([1])
    expect(p!.dows).toEqual([0])
  })

  it('returns null for invalid expressions', () => {
    expect(parseCron('60 16 * * 1-5')).toBeNull()
    expect(parseCron('* * * * * *')).toBeNull()
    expect(parseCron('hello')).toBeNull()
    expect(parseCron('')).toBeNull()
  })
})

describe('cronZh', () => {
  it('formats weekday single time', () => {
    expect(cronZh('30 16 * * 1-5')).toBe('工作日 16:30')
  })

  it('formats band schedule', () => {
    expect(cronZh('*/5 9-15 * * 1-5')).toBe('工作日 09–15 每 5 分钟')
    expect(cronZh('* * * * *')).toBe('每天 每分钟')
    expect(cronZh('0/30 * * * *')).toBe('每天 每 30 分钟')
  })

  it('formats multiple times with cap', () => {
    expect(cronZh('0 8,18 * * *')).toBe('每天 08:00、18:00')
    expect(cronZh('0 8 * * 0')).toBe('周日 08:00')
  })

  it('returns null for unparseable or dom/month restricted', () => {
    expect(cronZh(null)).toBeNull()
    expect(cronZh('hello world')).toBeNull()
    expect(cronZh('0 3 1 * *')).toBeNull()
  })
})

describe('nextRuns', () => {
  it('returns same-day future run in Beijing wall clock', () => {
    const runs = nextRuns('30 16 * * 1-5', 3, FROM)!
    expect(runs).toHaveLength(3)
    // 返回对象承诺北京墙钟表示（+480）：直接 format 断言，禁止再套 utcOffset
    expect(runs[0].utcOffset()).toBe(480)
    expect(runs[0].format('YYYY-MM-DD HH:mm')).toBe('2026-09-17 16:30')
    expect(runs[1].format('YYYY-MM-DD HH:mm')).toBe('2026-09-18 16:30')
    expect(runs[2].format('YYYY-MM-DD HH:mm')).toBe('2026-09-21 16:30')
  })

  it('skips weekend and past times for weekday cron', () => {
    // FROM 当日 08:00 已过（FROM=10:00）；09-19 周六 / 09-20 周日跳过
    const runs = nextRuns('0 8 * * 1-5', 3, FROM)!
    expect(runs.map((t) => t.format('MM-DD'))).toEqual(['09-18', '09-21', '09-22'])
  })

  it('skips missing day-of-month (month-end boundary)', () => {
    const runs = nextRuns('0 3 31 * *', 2, dayjs('2026-01-30T00:00:00+08:00'))!
    expect(runs.map((t) => t.format('YYYY-MM-DD'))).toEqual(['2026-01-31', '2026-03-31'])
  })

  it('returns null for unparseable expression', () => {
    expect(nextRuns('nope', 3, FROM)).toBeNull()
  })
})

describe('runsOnDate', () => {
  it('returns sorted minutes of matching day', () => {
    expect(runsOnDate('30 16 * * 1-5', dayjs('2026-09-16T00:00:00+08:00'))).toEqual([990])
    expect(runsOnDate('0 8,18 * * *', dayjs('2026-09-16T00:00:00+08:00'))).toEqual([
      8 * 60,
      18 * 60,
    ])
  })

  it('returns empty array for non-matching day', () => {
    // 2026-09-20 周日
    expect(runsOnDate('30 16 * * 1-5', dayjs('2026-09-20T00:00:00+08:00'))).toEqual([])
  })

  it('applies standard cron DOM/DOW OR semantics', () => {
    // dom=1 或周一即触发
    const expr = '0 3 1 * 1'
    // 2026-09-07 周一（非 1 日）命中；2026-09-01 周二（1 日）命中；09-08 周二不命中
    expect(runsOnDate(expr, dayjs('2026-09-07T00:00:00+08:00'))).toEqual([180])
    expect(runsOnDate(expr, dayjs('2026-09-01T00:00:00+08:00'))).toEqual([180])
    expect(runsOnDate(expr, dayjs('2026-09-08T00:00:00+08:00'))).toEqual([])
  })

  it('returns null for unparseable expression', () => {
    expect(runsOnDate('bad', dayjs('2026-09-17T00:00:00+08:00'))).toBeNull()
  })
})

describe('formatNextRunLabel', () => {
  it('labels today / tomorrow / weekday', () => {
    expect(formatNextRunLabel(dayjs('2026-09-17T16:30:00+08:00'), FROM)).toBe('今天 16:30')
    expect(formatNextRunLabel(dayjs('2026-09-18T16:30:00+08:00'), FROM)).toBe('明天 16:30')
    expect(formatNextRunLabel(dayjs('2026-09-21T16:30:00+08:00'), FROM)).toBe('周一 16:30')
  })
})

describe('consistency', () => {
  it('nextRuns stay consistent with runsOnDate', () => {
    const expr = '*/5 9-15 * * 1-5'
    const runs = nextRuns(expr, 5, FROM)!
    for (const t of runs) {
      const minutes = runsOnDate(expr, t)!
      expect(minutes).toContain(t.hour() * 60 + t.minute())
    }
  })
})
