/** reviewMetricsMeta 测试：指标行单源、跨窗口子集、null 展示与格式化口径。 */
import { describe, expect, it } from 'vitest'

import type { ApiTradingAgentReviewMetrics } from '@ai-invest/shared'

import {
  COMPARE_METRIC_ROWS,
  formatMetricValue,
  REVIEW_METRIC_ROWS,
} from './reviewMetricsMeta'

function metrics(overrides: Partial<ApiTradingAgentReviewMetrics> = {}): ApiTradingAgentReviewMetrics {
  return {
    period: 'month',
    startDate: '2026-09-01',
    endDate: '2026-09-30',
    tradingDays: 20,
    coveredStart: null,
    coveredEnd: null,
    startValue: null,
    endValue: null,
    returnPct: 8.5,
    annualizedReturnPct: null,
    maxDrawdownPct: 3.2,
    sellCount: 10,
    winRatePct: 60,
    profitLossRatio: 1.8,
    turnoverRatePct: 120,
    executionDeviationPct: -1.5,
    benchmarkReturnPct: 2.1,
    excessReturnPct: 6.4,
    notes: [],
    ...overrides,
  }
}

describe('reviewMetricsMeta', () => {
  it('指标卡与对比表共用同一行定义，对比表去掉仅卡片指标', () => {
    expect(REVIEW_METRIC_ROWS.map((row) => row.key)).toEqual([
      'returnPct',
      'annualizedReturnPct',
      'maxDrawdownPct',
      'excessReturnPct',
      'benchmarkReturnPct',
      'winRatePct',
      'profitLossRatio',
      'turnoverRatePct',
      'executionDeviationPct',
    ])
    expect(COMPARE_METRIC_ROWS.map((row) => row.key)).not.toContain('benchmarkReturnPct')
    expect(COMPARE_METRIC_ROWS).toHaveLength(REVIEW_METRIC_ROWS.length - 1)
  })

  it('取值走 row.pick，null 统一展示「-」', () => {
    const byKey = new Map(REVIEW_METRIC_ROWS.map((row) => [row.key, row]))
    const returnRow = byKey.get('returnPct')!
    const annualizedRow = byKey.get('annualizedReturnPct')!

    expect(formatMetricValue(returnRow, returnRow.pick(metrics()))).toBe('+8.50%')
    expect(formatMetricValue(annualizedRow, annualizedRow.pick(metrics()))).toBe('-')
  })

  it('回撤与盈亏比保留既有格式', () => {
    const byKey = new Map(REVIEW_METRIC_ROWS.map((row) => [row.key, row]))
    const drawdownRow = byKey.get('maxDrawdownPct')!
    const ratioRow = byKey.get('profitLossRatio')!

    expect(formatMetricValue(drawdownRow, drawdownRow.pick(metrics()))).toBe('-3.20%')
    expect(formatMetricValue(ratioRow, ratioRow.pick(metrics()))).toBe('1.80')
  })
})
