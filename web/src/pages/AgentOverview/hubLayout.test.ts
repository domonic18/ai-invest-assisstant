import { describe, expect, it } from 'vitest'

import { RING_STATIONS, layoutHub } from './hubLayout'

describe('layoutHub', () => {
  it('puts paper hub at center and ring stations evenly from top', () => {
    const { center, stations } = layoutHub(1000, 1000, 3)
    expect(stations.paper).toEqual(center)
    expect(center).toEqual({ x: 500, y: 500 })
    expect(stations.kb.x).toBeCloseTo(500)
    expect(stations.kb.y).toBeCloseTo(280)
    expect(stations.review.x).toBeCloseTo(720)
    expect(stations.review.y).toBeCloseTo(500)
    expect(stations.news.x).toBeCloseTo(500)
    expect(stations.news.y).toBeCloseTo(720)
    expect(stations.sentiment.x).toBeCloseTo(280)
    expect(stations.sentiment.y).toBeCloseTo(500)
  })

  it('places up to 8 agents on a single outer radius evenly', () => {
    const { center, agents } = layoutHub(1000, 1000, 3)
    expect(agents).toHaveLength(3)
    // 首槽自顶部起
    expect(agents[0].x).toBeCloseTo(500)
    expect(agents[0].y).toBeCloseTo(120)
    // 均匀角度 → 等距圆周
    const radius = (p: { x: number; y: number }) =>
      Math.hypot(p.x - center.x, p.y - center.y)
    expect(radius(agents[1])).toBeCloseTo(radius(agents[0]))
    expect(radius(agents[2])).toBeCloseTo(radius(agents[0]))
  })

  it('alternates dual radii when agents exceed 8 slots', () => {
    const { center, agents } = layoutHub(1000, 1000, 9)
    expect(agents).toHaveLength(9)
    const radius = (p: { x: number; y: number }) =>
      Math.hypot(p.x - center.x, p.y - center.y)
    expect(radius(agents[0])).toBeCloseTo(380)
    expect(radius(agents[1])).toBeCloseTo(380 * 0.84)
    expect(radius(agents[2])).toBeCloseTo(380)
  })

  it('keeps all nodes inside the container on small stages', () => {
    const { stations, agents } = layoutHub(400, 300, 12)
    for (const p of [...Object.values(stations), ...agents]) {
      expect(p.x).toBeGreaterThanOrEqual(52)
      expect(p.x).toBeLessThanOrEqual(348)
      expect(p.y).toBeGreaterThanOrEqual(52)
      expect(p.y).toBeLessThanOrEqual(248)
    }
  })

  it('returns no agent slots for zero agents', () => {
    const { agents } = layoutHub(1000, 1000, 0)
    expect(agents).toHaveLength(0)
  })

  it('ring order starts with kb', () => {
    expect(RING_STATIONS[0]).toBe('kb')
    expect(RING_STATIONS).not.toContain('paper')
  })
})
