import type { AgentOverviewItem, TradingAgentProfile } from '@ai-invest/shared'
import { describe, expect, it } from 'vitest'

import { buildHubEdges, edgeDecay } from './hubEdges'

const MINUTE_MS = 60_000

function makeProfile(overrides: Partial<TradingAgentProfile> = {}): TradingAgentProfile {
  return {
    agentKey: 'short-line',
    name: '短线猎手',
    tagline: '',
    llmConfigId: null,
    methodologySourceId: null,
    riskMaxPositionPct: 20,
    riskMaxTotalPct: 80,
    riskMaxDailyOrders: 10,
    intradayExecMode: 'shadow',
    intradayPaused: false,
    calibrationMode: 'shadow',
    status: 'active',
    planCadence: 'daily',
    reviewCadence: 'daily',
    sortOrder: 1,
    promptId: 'trading_agent_short_line',
    accentColor: '#3b82f6',
    ...overrides,
  }
}

function makeItem(overrides: Partial<AgentOverviewItem> = {}): AgentOverviewItem {
  return {
    profile: makeProfile(),
    llmName: null,
    runtimeState: 'idle',
    stateLabel: '待命',
    accountName: null,
    planCount: 0,
    selectionCount: 0,
    orderCount: 0,
    recentActivity: [],
    nextTasks: [],
    ...overrides,
  }
}

describe('edgeDecay', () => {
  it('returns still for missing timestamp', () => {
    expect(edgeDecay(null)).toEqual({ speed: 'still', opacity: 0.18 })
  })

  it('returns fast within 30 minutes', () => {
    const recent = new Date(Date.now() - 5 * MINUTE_MS).toISOString()
    expect(edgeDecay(recent)).toEqual({ speed: 'fast', opacity: 0.9 })
  })

  it('returns slow within 6 hours', () => {
    const hoursAgo = new Date(Date.now() - 120 * MINUTE_MS).toISOString()
    expect(edgeDecay(hoursAgo)).toEqual({ speed: 'slow', opacity: 0.5 })
  })

  it('returns still beyond 6 hours', () => {
    const daysAgo = new Date(Date.now() - 7 * 24 * 60 * MINUTE_MS).toISOString()
    expect(edgeDecay(daysAgo)).toEqual({ speed: 'still', opacity: 0.18 })
  })
})

describe('buildHubEdges', () => {
  it('draws plan-input edge for every active agent only', () => {
    const items = [
      makeItem(),
      makeItem({ profile: makeProfile({ agentKey: 'm60', status: 'planned' }) }),
    ]
    const edges = buildHubEdges(items)
    const targets = edges.filter((e) => e.toAgent !== null).map((e) => e.toAgent)
    expect(targets).toContain('short-line')
    expect(targets).not.toContain('m60')
    expect(edges.find((e) => e.id === 'review->short-line')?.kind).toBe('plan-input')
  })

  it('gates methodology and account edges on bindings', () => {
    const bound = makeItem({
      profile: makeProfile({ agentKey: 'a', methodologySourceId: 3 }),
      accountName: 'agent模拟盘',
    })
    const unbound = makeItem({ profile: makeProfile({ agentKey: 'b' }) })
    const edges = buildHubEdges([bound, unbound])
    expect(edges.some((e) => e.id === 'kb->a' && e.kind === 'methodology')).toBe(true)
    expect(edges.some((e) => e.id === 'paper->a' && e.kind === 'account')).toBe(true)
    expect(edges.some((e) => e.id === 'kb->b')).toBe(false)
    expect(edges.some((e) => e.id === 'paper->b')).toBe(false)
  })

  it('always adds news/sentiment upstream edges into review', () => {
    const edges = buildHubEdges([])
    const upstream = edges.filter((e) => e.kind === 'upstream')
    expect(upstream.map((e) => e.id).sort()).toEqual(['news->review', 'sentiment->review'])
    expect(upstream.every((e) => e.toAgent === null && e.from !== 'review')).toBe(true)
  })

  it('propagates agent activity freshness into edge speed', () => {
    const fresh = makeItem({
      recentActivity: [
        { kind: 'plan', title: '买入计划', occurredAt: new Date(Date.now() - 2 * MINUTE_MS).toISOString() },
      ],
    })
    const stale = makeItem({ profile: makeProfile({ agentKey: 'old' }) })
    const edges = buildHubEdges([fresh, stale])
    expect(edges.find((e) => e.id === 'review->short-line')?.speed).toBe('fast')
    expect(edges.find((e) => e.id === 'review->old')?.speed).toBe('still')
  })
})
