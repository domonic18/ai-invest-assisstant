import { describe, expect, it } from 'vitest'

import { normalizeHexColor } from './color'

describe('normalizeHexColor', () => {
  it('keeps 6-digit hex unchanged', () => {
    expect(normalizeHexColor('#f0b429')).toBe('#f0b429')
    expect(normalizeHexColor('#F0B429')).toBe('#F0B429')
  })

  it('drops alpha from 8-digit hex', () => {
    expect(normalizeHexColor('#f0b429ff')).toBe('#f0b429')
    expect(normalizeHexColor('#f0b42980')).toBe('#f0b429')
  })

  it('converts rgb() to hex', () => {
    expect(normalizeHexColor('rgb(0,247,8)')).toBe('#00f708')
    expect(normalizeHexColor('rgb(240, 180, 41)')).toBe('#f0b429')
  })

  it('returns unrecognized input unchanged', () => {
    expect(normalizeHexColor('red')).toBe('red')
    expect(normalizeHexColor('rgb(300,1,1)')).toBe('rgb(300,1,1)')
  })
})
