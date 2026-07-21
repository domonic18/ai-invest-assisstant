import { describe, expect, it } from 'vitest'

import { formatSealTime } from './formatters'

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
