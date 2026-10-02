import { describe, expect, it } from 'vitest'

import { DAY_TICKS, beijingMinutes, groupPulses, minutesToX } from './timeAxis'

describe('minutesToX', () => {
  it('09:25 → 150（波形区起点）', () => {
    expect(minutesToX(9 * 60 + 25)).toBe(150)
  })

  it('18:35 → 345（波形区终点）', () => {
    expect(minutesToX(18 * 60 + 35)).toBe(345)
  })

  it('越界钳制到 [150,345]', () => {
    expect(minutesToX(0)).toBe(150)
    expect(minutesToX(24 * 60)).toBe(345)
  })
})

describe('beijingMinutes', () => {
  it('解析 +08:00 时间串为北京分钟数', () => {
    expect(beijingMinutes('2026-09-30T09:30:00+08:00')).toBe(570)
    expect(beijingMinutes('2026-09-30T13:20:00+08:00')).toBe(800)
  })

  it('UTC 串按北京墙钟换算', () => {
    expect(beijingMinutes('2026-09-30T01:30:00Z')).toBe(570)
  })

  it('非法输入返回 null', () => {
    expect(beijingMinutes('not-a-time')).toBeNull()
  })
})

describe('DAY_TICKS', () => {
  it('覆盖 09:30—18:35 业务日程', () => {
    expect(DAY_TICKS[0]).toEqual({ label: '09:30', min: 570 })
    expect(DAY_TICKS[DAY_TICKS.length - 1]).toEqual({ label: '18:35', min: 1115 })
  })
})

describe('groupPulses', () => {
  it('相邻 <7px 的分钟点合并为脉冲块（密度=节奏）', () => {
    const groups = groupPulses([570, 575, 580, 800])
    expect(groups).toHaveLength(2)
    expect(groups[0].count).toBe(3)
    expect(groups[1].count).toBe(1)
  })

  it('空输入 → 空数组', () => {
    expect(groupPulses([])).toEqual([])
  })
})
