import { describe, expect, it } from 'vitest'

import { movingAverage } from './movingAverage'

describe('movingAverage', () => {
  it('returns nulls until the window fills', () => {
    expect(movingAverage([1, 2, 3, 4], 3)).toEqual([null, null, 2, 3])
  })

  it('handles window of 1', () => {
    expect(movingAverage([5, 6], 1)).toEqual([5, 6])
  })

  it('propagates nulls through the window', () => {
    expect(movingAverage([1, null, 3, 4, 5], 3)).toEqual([null, null, null, null, 4])
  })

  it('recovers after nulls leave the window', () => {
    expect(movingAverage([null, 2, 4, 6], 2)).toEqual([null, null, 3, 5])
  })

  it('returns all nulls for empty input', () => {
    expect(movingAverage([], 5)).toEqual([])
  })
})
