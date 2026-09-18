/** 北京墙钟基础设施的性质测试：幂等、瞬时不变、跨表示输入墙钟恒北京。
 * 全部断言由显式偏移 fixture 推导，与 runner 时区无关（CI UTC 即免费第二时区）。 */

import { describe, expect, it } from 'vitest'
import dayjs from 'dayjs'

import { BJ_OFFSET_MIN, bjDayMatches, bjNow, toBeijing } from './beijing'
import { formatNextRunLabel } from './cron'

describe('toBeijing', () => {
  it('任意表示的输入都归一到 +480 且瞬时不变', () => {
    const inputs = [
      dayjs('2026-09-17T10:00:00+08:00'), // 带偏移字符串：表示随运行环境
      dayjs('2026-09-17T02:00:00Z'), // UTC 字符串：同上
      dayjs('2026-09-17T02:00:00Z').utcOffset(BJ_OFFSET_MIN), // 已是北京表示
    ]
    for (const input of inputs) {
      const bj = toBeijing(input)
      expect(bj.utcOffset()).toBe(BJ_OFFSET_MIN)
      expect(bj.toISOString()).toBe(input.toISOString())
    }
  })

  it('幂等：对北京表示对象重复转换是 no-op', () => {
    const once = toBeijing(dayjs('2026-09-17T02:00:00Z'))
    const twice = toBeijing(once)
    expect(twice.toISOString()).toBe(once.toISOString())
    expect(twice.format('YYYY-MM-DD HH:mm')).toBe(once.format('YYYY-MM-DD HH:mm'))
  })
})

describe('bjNow', () => {
  it('返回北京墙钟表示', () => {
    expect(bjNow().utcOffset()).toBe(BJ_OFFSET_MIN)
  })
})

describe('bjDayMatches', () => {
  const base = { months: null, doms: null, dows: null }

  it('dom 与 dow 同时受限取 OR（标准 cron 语义）', () => {
    // 2026-09-17 周四（dom=17）；2026-09-21 周一（dom=21）
    const thursday = toBeijing(dayjs('2026-09-17T10:00:00+08:00'))
    expect(bjDayMatches({ ...base, doms: [1], dows: [4] }, thursday)).toBe(true)
    expect(bjDayMatches({ ...base, doms: [1], dows: [1] }, thursday)).toBe(false)
  })

  it('仅单边受限时必须命中该边', () => {
    const sunday = toBeijing(dayjs('2026-09-20T10:00:00+08:00'))
    expect(bjDayMatches({ ...base, dows: [0] }, sunday)).toBe(true)
    expect(bjDayMatches({ ...base, dows: [1] }, sunday)).toBe(false)
    expect(bjDayMatches({ ...base, doms: [20] }, sunday)).toBe(true)
  })
})

describe('formatNextRunLabel 与北京表示契约', () => {
  it('同一瞬时、不同表示的输入产出同一标签', () => {
    const from = dayjs('2026-09-17T10:00:00+08:00')
    const localRep = dayjs('2026-09-17T08:30:00Z') // 与北京 16:30 同瞬时
    const bjRep = toBeijing(localRep)
    expect(formatNextRunLabel(localRep, from)).toBe(formatNextRunLabel(bjRep, from))
    expect(formatNextRunLabel(localRep, from)).toBe('今天 16:30')
  })

  it('星期前缀按北京墙钟取日', () => {
    // 北京 2026-09-21（周一）00:30 = UTC 09-20 16:30；UTC 墙钟会误报周日
    const from = dayjs('2026-09-18T10:00:00+08:00')
    const bjMondayMidnight = dayjs('2026-09-21T00:30:00+08:00')
    expect(formatNextRunLabel(bjMondayMidnight, from)).toBe('周一 00:30')
  })
})
