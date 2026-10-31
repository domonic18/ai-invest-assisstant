/** 复盘确定性指标展示元数据单一真相源（指标卡与跨窗口对比共用 label / 取值 / 格式 / 着色）。 */

import type { ApiTradingAgentReviewMetrics } from '@ai-invest/shared'

import { changeHex, fallHex, formatNumber, formatPercent } from '@/utils/formatters'

/** 着色口径：change=涨跌正负着色；drawdown=固定回撤色；plain=中性。 */
export type ReviewMetricTone = 'change' | 'drawdown' | 'plain'

export interface ReviewMetricRow {
  key: string
  label: string
  /** 从指标对象取值；null = 不可计算。 */
  pick: (metrics: ApiTradingAgentReviewMetrics) => number | null
  /** 非空值的展示文本（百分比口径在此统一）。 */
  format: (value: number) => string
  tone: ReviewMetricTone
  /** 跨窗口对比表是否展示（false 表示仅指标卡展示）。 */
  comparable?: boolean
}

export const REVIEW_METRIC_ROWS: readonly ReviewMetricRow[] = [
  {
    key: 'returnPct',
    label: '区间收益',
    pick: (m) => m.returnPct,
    format: formatPercent,
    tone: 'change',
  },
  {
    key: 'annualizedReturnPct',
    label: '年化收益',
    pick: (m) => m.annualizedReturnPct,
    format: formatPercent,
    tone: 'change',
  },
  {
    key: 'maxDrawdownPct',
    label: '最大回撤',
    pick: (m) => m.maxDrawdownPct,
    format: (v) => `-${formatNumber(v)}%`,
    tone: 'drawdown',
  },
  {
    key: 'excessReturnPct',
    label: '超额收益',
    pick: (m) => m.excessReturnPct,
    format: formatPercent,
    tone: 'change',
  },
  {
    key: 'benchmarkReturnPct',
    label: '沪深300',
    pick: (m) => m.benchmarkReturnPct,
    format: formatPercent,
    tone: 'change',
    comparable: false,
  },
  {
    key: 'winRatePct',
    label: '胜率',
    pick: (m) => m.winRatePct,
    format: formatPercent,
    tone: 'plain',
  },
  {
    key: 'profitLossRatio',
    label: '盈亏比',
    pick: (m) => m.profitLossRatio,
    format: (v) => formatNumber(v),
    tone: 'plain',
  },
  {
    key: 'turnoverRatePct',
    label: '换手率',
    pick: (m) => m.turnoverRatePct,
    format: formatPercent,
    tone: 'plain',
  },
  {
    key: 'executionDeviationPct',
    label: '执行偏差',
    pick: (m) => m.executionDeviationPct,
    format: formatPercent,
    tone: 'plain',
  },
]

/** 跨窗口对比表展示的指标（与指标卡同一口径，去掉仅指标卡有用的行）。 */
export const COMPARE_METRIC_ROWS: readonly ReviewMetricRow[] = REVIEW_METRIC_ROWS.filter(
  (row) => row.comparable !== false,
)

/** 非空值的展示文本；不可计算统一「-」。 */
export function formatMetricValue(row: ReviewMetricRow, value: number | null): string {
  return value === null ? '-' : row.format(value)
}

/** 指标卡着色：收益类按正负、回撤固定下跌色、比率类中性。 */
export function metricColor(
  value: number | null | undefined,
  tone: ReviewMetricTone,
): string | undefined {
  if (value === null || value === undefined || tone === 'plain') return undefined
  return tone === 'drawdown' ? fallHex() : changeHex(value)
}

/** 跨窗口对比表着色：仅收益类着色（回撤行保持中性，与卡片口径区分）。 */
export function compareMetricColor(
  value: number | null | undefined,
  tone: ReviewMetricTone,
): string | undefined {
  if (value === null || value === undefined || tone !== 'change') return undefined
  return changeHex(value)
}
