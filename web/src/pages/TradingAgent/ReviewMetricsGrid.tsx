/** 复盘确定性指标卡（系统计算，LLM 只解读；null 显示「-」）。 */

import { Typography } from 'antd'

import type { ApiTradingAgentReviewMetrics } from '@ai-invest/shared'

import { useColorScheme } from '@/stores/settings'
import { changeHex, fallHex, formatNumber, formatPercent } from '@/utils/formatters'

interface MetricCell {
  label: string
  value: string
  color?: string
}

function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? '-' : formatPercent(value)
}

function buildCells(metrics: ApiTradingAgentReviewMetrics): MetricCell[] {
  return [
    { label: '区间收益', value: pct(metrics.returnPct), color: changeHex(metrics.returnPct) },
    {
      label: '年化收益',
      value: pct(metrics.annualizedReturnPct),
      color: changeHex(metrics.annualizedReturnPct),
    },
    {
      label: '最大回撤',
      value:
        metrics.maxDrawdownPct === null
          ? '-'
          : `-${formatNumber(metrics.maxDrawdownPct)}%`,
      color: metrics.maxDrawdownPct === null ? undefined : fallHex(),
    },
    {
      label: '超额收益',
      value: pct(metrics.excessReturnPct),
      color: changeHex(metrics.excessReturnPct),
    },
    {
      label: '沪深300',
      value: pct(metrics.benchmarkReturnPct),
      color: changeHex(metrics.benchmarkReturnPct),
    },
    { label: '胜率', value: pct(metrics.winRatePct) },
    {
      label: '盈亏比',
      value:
        metrics.profitLossRatio === null ? '-' : formatNumber(metrics.profitLossRatio),
    },
    { label: '换手率', value: pct(metrics.turnoverRatePct) },
    { label: '执行偏差', value: pct(metrics.executionDeviationPct) },
    { label: '卖出笔数', value: String(metrics.sellCount) },
  ]
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
