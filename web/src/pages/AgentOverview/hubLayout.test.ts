import { describe, expect, it } from 'vitest'

import { INFRA_IDS, RING_STATIONS, layoutLayers } from './hubLayout'

describe('layoutLayers', () => {
  it('places agents on a single row evenly inside the agent band', () => {
    const { agents } = layoutLayers(1000, 1000, 3, 0)
    expect(agents).toHaveLength(3)
    expect(agents[0].x).toBeCloseTo(250)
    expect(agents[1].x).toBeCloseTo(500)
    expect(agents[2].x).toBeCloseTo(750)
    for (const p of agents) expect(p.y).toBeCloseTo(160)
  })

  it('lays five stations on the same band at equal width (paper not special)', () => {
    const { stations } = layoutLayers(1000, 1000, 0, 0)
    expect(Object.keys(stations)).toHaveLength(RING_STATIONS.length)
    for (const p of Object.values(stations)) expect(p.y).toBeCloseTo(460)
    expect(stations.kb.x).toBeCloseTo(1000 / 6)
    expect(stations.review.x).toBeCloseTo((1000 * 2) / 6)
    expect(stations.paper.x).toBeCloseTo((1000 * 5) / 6)
  })

  it('lays five infra boxes on the infra band', () => {
    const { infra } = layoutLayers(1000, 1000, 0, 0)
    expect(Object.keys(infra)).toHaveLength(INFRA_IDS.length)
    for (const p of Object.values(infra)) expect(p.y).toBeCloseTo(740)
    expect(infra.postgres.x).toBeCloseTo(1000 / 6)
    expect(infra.minio.x).toBeCloseTo((1000 * 5) / 6)
  })

  it('places one anchor per celery queue on the bottom band', () => {
    const { queues } = layoutLayers(1000, 1000, 0, 3)
    expect(queues).toHaveLength(3)
    for (const p of queues) expect(p.y).toBeCloseTo(920)
    expect(queues[0].x).toBeCloseTo(250)
    expect(queues[1].x).toBeCloseTo(500)
    expect(queues[2].x).toBeCloseTo(750)
  })

  it('keeps all nodes inside the container on small stages', () => {
    const { stations, agents, infra, queues } = layoutLayers(400, 300, 12, 3)
    for (const p of [...Object.values(stations), ...agents, ...Object.values(infra), ...queues]) {
      expect(p.x).toBeGreaterThanOrEqual(56)
      expect(p.x).toBeLessThanOrEqual(344)
      expect(p.y).toBeGreaterThanOrEqual(56)
      expect(p.y).toBeLessThanOrEqual(244)
    }
  })

  it('returns no agent slots for zero agents', () => {
    const { agents } = layoutLayers(1000, 1000, 0, 0)
    expect(agents).toHaveLength(0)
  })

  it('station order keeps paper as an ordinary member of the ring', () => {
    expect(RING_STATIONS).toEqual(['kb', 'review', 'news', 'sentiment', 'paper'])
  })
})
