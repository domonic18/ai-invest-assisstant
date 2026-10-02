/** observationMeta 纯函数测试：一句话结论组合、score/confidence 分档边界、分时方向词。 */
import { describe, expect, it } from 'vitest'

import type { ApiTradingAgentObservationItem } from '@ai-invest/shared'

import {
  confidenceBand,
  fmtConfidence,
  fmtScore,
  noulLabel,
  observationSummary,
  scoreBand,
} from './observationMeta'

function item(overrides: Partial<ApiTradingAgentObservationItem> = {}): ApiTradingAgentObservationItem {
  return {
    id: 1,
    tickTime: '2026-09-29T01:30:00Z',
    tradeDate: '2026-09-29',
    agentKey: 'short-line',
    planId: 11,
    stockCode: '600000',
    stockName: '浦发银行',
    planType: 'sell',
    price: 10.0,
    changePct: 1.01,
    l0Verdict: 'triggered',
    triggerReason: 'buy_zone',
    l0Detail: null,
    decision: {
      servedModel: 'openjev-0.1',
      choice: '立即执行',
      confidence: 0.52,
      noul: true,
      score: 3,
      window: null,
    },
    action: 'suppress',
    suppressionReason: 'below_threshold',
    isShadow: true,
    clOrdId: null,
    orderVolume: null,
    ...overrides,
  }
}

describe('observationSummary', () => {
  it('no_action 心跳行给出巡检结论', () => {
    expect(
      observationSummary(item({ l0Verdict: 'no_action', action: null, suppressionReason: null, l0Detail: '未触达止盈/止损价' })),
    ).toBe('巡检正常 · 未触达止盈/止损价')
  })

  it('no_action 缺 l0Detail 时兜底', () => {
    expect(observationSummary(item({ l0Verdict: 'no_action', action: null, suppressionReason: null }))).toBe(
      '巡检正常 · 未触达触发价',
    )
  })

  it('no_action + l0_reject 是纪律否决', () => {
    expect(
      observationSummary(
        item({ l0Verdict: 'no_action', action: null, suppressionReason: 'l0_reject', l0Detail: '现价 3.5 已跌破止损位 4.18' }),
      ),
    ).toBe('纪律否决：现价 3.5 已跌破止损位 4.18')
    expect(
      observationSummary(item({ l0Verdict: 'no_action', action: null, suppressionReason: 'l0_reject' })),
    ).toBe('纪律否决：触发前提失效')
  })

  it('near_trigger 行', () => {
    expect(
      observationSummary(item({ l0Verdict: 'near_trigger', action: 'wait', suppressionReason: null, l0Detail: '低于买点区间，等待回踩' })),
    ).toBe('接近触发 · 低于买点区间，等待回踩')
    expect(observationSummary(item({ l0Verdict: 'near_trigger', action: 'wait', suppressionReason: null }))).toBe(
      '接近触发 · 等待回踩',
    )
  })

  it('triggered 按触发原因选短语', () => {
    const base = { action: 'execute' as const, suppressionReason: null }
    expect(observationSummary(item({ ...base, triggerReason: 'stop_loss' }))).toBe('击穿止损线，已下单执行')
    expect(observationSummary(item({ ...base, triggerReason: 'target' }))).toBe('触及止盈目标，已下单执行')
    expect(observationSummary(item({ ...base, triggerReason: 'buy_zone' }))).toBe('进入买点区间，已下单执行')
  })

  it('triggered + abandon/wait 结论带模型选择', () => {
    expect(
      observationSummary(
        item({ triggerReason: 'stop_loss', action: 'abandon', suppressionReason: null, decision: { servedModel: 'm', choice: '放弃本档', confidence: 0.14, noul: null, score: null, window: null } }),
      ),
    ).toBe('击穿止损线，模型选择放弃本档')
    expect(
      observationSummary(
        item({ triggerReason: 'target', action: 'wait', suppressionReason: null, decision: { servedModel: 'm', choice: '等待回踩', confidence: 0.7, noul: null, score: null, window: null } }),
      ),
    ).toBe('触及止盈目标，模型选择等待回踩')
  })

  it('triggered + 抑制结论按原因映射', () => {
    const base = { triggerReason: 'buy_zone' as const };
    (['shadow_mode', 'below_threshold', 'model_degraded', 'risk_rejected', 'position_unavailable', 'order_error', 'no_account'] as const).forEach(
      (reason) => {
        const text = observationSummary(item({ ...base, suppressionReason: reason }))
        expect(text).toContain('进入买点区间，')
        expect(text).not.toBe('进入买点区间')
      },
    )
    expect(observationSummary(item({ ...base, suppressionReason: 'shadow_mode' }))).toBe('进入买点区间，影子模式仅记录')
    expect(observationSummary(item({ ...base, suppressionReason: 'below_threshold' }))).toBe('进入买点区间，置信不足未执行')
    expect(observationSummary(item({ ...base, action: 'execute', suppressionReason: 'risk_rejected' }))).toBe(
      '进入买点区间，风控拒绝下单',
    )
  })

  it('tail_check 行按是否成交分句', () => {
    const tail = { planId: null, planType: null, stockName: null, triggerReason: 'stop_loss' as const, decision: { servedModel: null, choice: null, confidence: null, noul: null, score: null, window: 'tail_check' } }
    expect(observationSummary(item({ ...tail, action: 'execute', suppressionReason: 'shadow_mode' }))).toBe('尾盘强检：跌破止损，强制卖出')
    expect(observationSummary(item({ ...tail, action: 'suppress', suppressionReason: 'shadow_mode' }))).toBe('尾盘强检：跌破止损，仅记录')
  })

  it('degraded 行', () => {
    expect(observationSummary(item({ l0Verdict: 'degraded', action: 'suppress', suppressionReason: 'model_degraded' }))).toBe(
      '模型降级 · 仅按确定性规则巡检',
    )
  })
})

describe('scoreBand / fmtScore', () => {
  it('分档边界', () => {
    expect(scoreBand(1.5)).toBe('极弱')
    expect(scoreBand(1.51)).toBe('弱势')
    expect(scoreBand(2.5)).toBe('弱势')
    expect(scoreBand(2.6)).toBe('中性')
    expect(scoreBand(3.5)).toBe('中性')
    expect(scoreBand(3.6)).toBe('强势')
    expect(scoreBand(4.5)).toBe('强势')
    expect(scoreBand(4.6)).toBe('极强')
  })

  it('fmtScore 一位小数 + 档位', () => {
    expect(fmtScore(1.0770112008550798)).toBe('1.1/5 · 极弱')
    expect(fmtScore(3)).toBe('3.0/5 · 中性')
    expect(fmtScore(5)).toBe('5.0/5 · 极强')
  })
})

describe('confidenceBand / fmtConfidence', () => {
  it('分档边界对齐 L2 阈值', () => {
    expect(confidenceBand(0.59)).toBe('低')
    expect(confidenceBand(0.6)).toBe('中')
    expect(confidenceBand(0.84)).toBe('中')
    expect(confidenceBand(0.85)).toBe('高')
  })

  it('fmtConfidence 输出人话', () => {
    expect(fmtConfidence(0.14)).toBe('置信 14%（低）')
    expect(fmtConfidence(0.7)).toBe('置信 70%（中）')
    expect(fmtConfidence(0.86)).toBe('置信 86%（高）')
  })
})

describe('noulLabel', () => {
  it('按计划方向选词', () => {
    expect(noulLabel(true, 'sell')).toBe('分时：支持离场')
    expect(noulLabel(false, 'sell')).toBe('分时：不支持离场')
    expect(noulLabel(true, 'buy')).toBe('分时：支持买入')
    expect(noulLabel(false, 'buy')).toBe('分时：不支持买入')
    expect(noulLabel(true, null)).toBe('分时：支持买入')
  })
})
