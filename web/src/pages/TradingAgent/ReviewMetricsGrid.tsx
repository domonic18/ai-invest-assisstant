/** 复盘确定性指标卡（系统计算，LLM 只解读；null 显示「-」）。 */

import { Typography } from 'antd'

import type { ApiTradingAgentReviewMetrics } from '@ai-invest/shared'

import { useColorScheme } from '@/stores/settings'

import {
  formatMetricValue,
  metricColor,
  REVIEW_METRIC_ROWS,
  type ReviewMetricRow,
} from './reviewMetricsMeta'

interface MetricCell {
  label: string
  value: string
  color?: string
}

function buildCells(metrics: ApiTradingAgentReviewMetrics): MetricCell[] {
  const cells: MetricCell[] = REVIEW_METRIC_ROWS.map((row: ReviewMetricRow) => {
    const value = row.pick(metrics)
    return {
      label: row.label,
      value: formatMetricValue(row, value),
      color: metricColor(value, row.tone),
    }
  })
  cells.push({ label: '卖出笔数', value: String(metrics.sellCount) })
  return cells
}

export function ReviewMetricsGrid({ metrics }: { metrics: ApiTradingAgentReviewMetrics }) {
  useColorScheme()
  const cells = buildCells(metrics)
  const covered =
    metrics.coveredStart && metrics.coveredStart !== metrics.startDate
      ? `净值自 ${metrics.coveredStart} 起覆盖`
      : null

  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2.5">
      <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-white/50">
        <span>
          区间 {metrics.startDate} ~ {metrics.endDate}
        </span>
        <span>{metrics.tradingDays} 个交易日</span>
        {covered && <span>{covered}</span>}
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        {cells.map((cell) => (
          <div key={cell.label} className="flex flex-col">
            <span className="text-[11px] text-white/45">{cell.label}</span>
            <span className="text-sm font-medium tabular-nums" style={{ color: cell.color }}>
              {cell.value}
            </span>
          </div>
        ))}
      </div>
      {metrics.notes.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {metrics.notes.map((note) => (
            <li key={note}>
              <Typography.Text type="secondary" className="text-[11px]">
                · {note}
              </Typography.Text>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
