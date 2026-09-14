import { describe, expect, it } from 'vitest'

import {
  alignAnchorIndex,
  anchorToIndex,
  buildDateIndex,
  clipRect,
  clipSegment,
  extendRay,
  lineDashArray,
  roundPrice,
} from './geometry'

const DATES = ['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-07', '2026-09-08']

const GRID = { x: 46, y: 10, width: 800, height: 300 }

describe('buildDateIndex', () => {
  it('builds exact date → index map', () => {
    const idx = buildDateIndex(DATES)
    expect(idx.get('2026-09-03')).toBe(2)
    expect(idx.has('2026-09-05')).toBe(false)
  })
})

describe('alignAnchorIndex', () => {
  it('matches exact date', () => {
    expect(alignAnchorIndex('2026-09-03', DATES)).toBe(2)
  })

  it('aligns to last bar ≤ date across weekend gap', () => {
    expect(alignAnchorIndex('2026-09-05', DATES)).toBe(2)
    expect(alignAnchorIndex('2026-09-06', DATES)).toBe(2)
  })

  it('clamps beyond range to last bar, before range to first bar', () => {
    expect(alignAnchorIndex('2026-12-31', DATES)).toBe(4)
    expect(alignAnchorIndex('2020-01-01', DATES)).toBe(0)
  })

  it('empty anchor date pins to last bar; empty dates → -1', () => {
    expect(alignAnchorIndex('', DATES)).toBe(4)
    expect(alignAnchorIndex('2026-09-03', [])).toBe(-1)
  })
})

describe('anchorToIndex', () => {
  it('prefers exact hit then ≤ alignment', () => {
    expect(anchorToIndex({ date: '2026-09-07', price: 10 }, DATES)).toBe(3)
    expect(anchorToIndex({ date: '2026-09-05', price: 10 }, DATES)).toBe(2)
  })
})

describe('roundPrice', () => {
  it('rounds to 2 decimals', () => {
    expect(roundPrice(10.126)).toBe(10.13)
    expect(roundPrice(10.1234)).toBe(10.12)
  })
})

describe('clipSegment', () => {
  it('keeps segment fully inside', () => {
    const out = clipSegment({ x: 100, y: 50 }, { x: 300, y: 80 }, GRID)
    expect(out).toEqual([{ x: 100, y: 50 }, { x: 300, y: 80 }])
  })

  it('clips segment crossing the left edge', () => {
    const out = clipSegment({ x: 0, y: 160 }, { x: 200, y: 160 }, GRID)
    expect(out).not.toBeNull()
    expect(out![0].x).toBe(46)
    expect(out![1].x).toBe(200)
  })

  it('returns null when fully outside', () => {
    expect(clipSegment({ x: 0, y: 5 }, { x: 30, y: 5 }, GRID)).toBeNull()
    expect(clipSegment({ x: 100, y: 400 }, { x: 300, y: 500 }, GRID)).toBeNull()
  })

  it('handles vertical segment', () => {
    const out = clipSegment({ x: 200, y: -50 }, { x: 200, y: 200 }, GRID)
    expect(out).not.toBeNull()
    expect(out![0].y).toBe(10)
    expect(out![1].y).toBe(200)
  })
})

describe('clipRect', () => {
  it('intersects box with grid', () => {
    const out = clipRect({ x: 0, y: 50 }, { x: 200, y: 100 }, GRID)
    expect(out).toEqual({ x: 46, y: 50, width: 154, height: 50 })
  })

  it('returns null when disjoint', () => {
    expect(clipRect({ x: 0, y: 0 }, { x: 10, y: 5 }, GRID)).toBeNull()
  })
})

describe('extendRay', () => {
  it('extends rightward to grid right edge keeping slope', () => {
    const [s, e] = extendRay({ x: 100, y: 100 }, { x: 200, y: 150 }, GRID, 'right')
    expect(s).toEqual({ x: 100, y: 100 })
    expect(e.x).toBe(846)
    expect(e.y).toBeCloseTo(100 + ((846 - 100) / 100) * 50)
  })

  it('extends leftward from first anchor to grid left edge', () => {
    const [s, e] = extendRay({ x: 300, y: 100 }, { x: 400, y: 150 }, GRID, 'left')
    expect(e).toEqual({ x: 400, y: 150 })
    expect(s.x).toBe(46)
    expect(s.y).toBeCloseTo(100 + ((46 - 300) / 100) * 50)
  })

  it('extends both directions', () => {
    const [s, e] = extendRay({ x: 300, y: 100 }, { x: 400, y: 150 }, GRID, 'both')
    expect(s.x).toBe(46)
    expect(e.x).toBe(846)
  })

  it('degenerate vertical ray spans grid vertically', () => {
    const [s, e] = extendRay({ x: 300, y: 100 }, { x: 300, y: 120 }, GRID, 'right')
    expect(s.x).toBe(300)
    expect(s.y).toBe(100)
    expect(e).toEqual({ x: 300, y: 310 })
  })
})

describe('lineDashArray', () => {
  it('maps styles to dash arrays', () => {
    expect(lineDashArray('solid')).toEqual([])
    expect(lineDashArray('dashed')).toEqual([7, 5])
    expect(lineDashArray('dotted')).toEqual([2, 5])
  })
})
