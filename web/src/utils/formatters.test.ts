import { describe, expect, it } from 'vitest'

import { formatCronExpression, formatSealTime } from './formatters'

describe('formatSealTime', () => {
  it('formats 6-digit seal time', () => {
    expect(formatSealTime('092500')).toBe('09:25:00')
    expect(formatSealTime('101215')).toBe('10:12:15')
    expect(formatSealTime('150000')).toBe('15:00:00')
  })

  it('pads short values', () => {
    expect(formatSealTime('92500')).toBe('09:25:00')
  })

  it('returns dash for empty values', () => {
    expect(formatSealTime(null)).toBe('-')
    expect(formatSealTime(undefined)).toBe('-')
    expect(formatSealTime('')).toBe('-')
  })
})

describe('formatCronExpression', () => {
  it('describes common schedules in Chinese', () => {
    expect(formatCronExpression('0 16 * * 1-5')).toContain('04:00')
    expect(formatCronExpression('0 16 * * 1-5')).toContain('星期一至星期五')
    expect(formatCronExpression('*/5 9-15 * * 1-5')).toContain('每隔 5 分钟')
  })

  it('returns dash for empty values', () => {
    expect(formatCronExpression(null)).toBe('-')
    expect(formatCronExpression(undefined)).toBe('-')
    expect(formatCronExpression('')).toBe('-')
  })

  it('falls back to raw expression on parse error', () => {
    expect(formatCronExpression('invalid')).toBe('invalid')
  })
})
