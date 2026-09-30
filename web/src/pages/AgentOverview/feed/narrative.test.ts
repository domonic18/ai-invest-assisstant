import { describe, expect, it } from 'vitest'

import type { ApiTradingAgentObservationItem } from '@ai-invest/shared'

import { toNarrative } from './narrative'

function obs(overrides: Partial<ApiTradingAgentObservationItem> = {}): ApiTradingAgentObservationItem {
  return {
    id: 1,
    tickTime: '2026-09-30T05:44:58+00:00', // 13:44:58 北京
    tradeDate: '2026-09-30',
    agentKey: 'hunter',
    planId: 1,
    stockCode: '600000',
    stockName: '浦发银行',
    planType: 'buy',
    price: 10.98,
    changePct: 1.2,
    l0Verdict: 'triggered',
    triggerReason: 'buy_zone',
    l0Detail: null,
    decision: null,
    action: null,
    suppressionReason: null,
    isShadow: true,
    clOrdId: 'X1',
    orderVolume: 900,
    ...overrides,
  }
}

describe('toNarrative', () => {
  it('execute → 买入执行 hot 卡片，股票名称+代号双写', () => {
    const card = toNarrative(obs({ action: 'execute' }))
    expect(card.tone).toBe('hot')
    expect(card.tag).toBe('买入执行')
    expect(card.sentence).toContain('浦发银行 600000')
    expect(card.sentence).toContain('10.98')
    expect(card.meta).toContain('BUY 600000')
    expect(card.meta).toContain('数量 900')
    expect(card.time).toBe('13:44:58')
  })

  it('卖出执行：planType=sell → SELL 文案', () => {
    const card = toNarrative(obs({ action: 'execute', planType: 'sell' }))
    expect(card.tag).toBe('卖出执行')
    expect(card.meta).toContain('SELL 600000')
  })

  it('suppress → 抑制 dim 卡片，附拒绝原因', () => {
    const card = toNarrative(
      obs({ action: 'suppress', suppressionReason: 'chase_high · 超买 30%', l0Verdict: 'no_action' }),
    )
    expect(card.tone).toBe('dim')
    expect(card.tag).toBe('抑制')
    expect(card.sentence).toContain('忍住了')
    expect(card.sentence).toContain('chase_high · 超买 30%')
  })

  it('wait / abandon → dim 观望与放弃', () => {
    expect(toNarrative(obs({ action: 'wait', l0Detail: '量未放大' })).tag).toBe('观望')
    const abandon = toNarrative(obs({ action: 'abandon', l0Detail: '跌破买区' }))
    expect(abandon.tag).toBe('放弃')
    expect(abandon.sentence).toContain('跌破买区')
  })

  it('尾盘强检行（decision.window）', () => {
    const card = toNarrative(
      obs({ decision: { servedModel: null, choice: null, confidence: null, noul: null, score: null, window: 'tail_check' } }),
    )
    expect(card.tag).toBe('尾盘强检')
  })

  it('near_trigger → 临近触发 norm', () => {
    const card = toNarrative(obs({ l0Verdict: 'near_trigger' }))
    expect(card.tone).toBe('norm')
    expect(card.tag).toBe('临近触发')
  })

  it('degraded → 体检告警', () => {
    const card = toNarrative(obs({ l0Verdict: 'degraded', l0Detail: '止损脱锚' }))
    expect(card.tag).toBe('体检告警')
    expect(card.sentence).toContain('止损脱锚')
  })

  it('默认心跳：无动作行 dim', () => {
    const card = toNarrative(obs({ l0Verdict: 'no_action', stockName: null }))
    expect(card.tone).toBe('dim')
    expect(card.tag).toBe('心跳')
    expect(card.sentence).toContain('600000')
    expect(card.meta).toContain('L0 no_action')
  })
})
