import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

import type { FinancialHealth } from '@ai-invest/shared'
import { FINANCIAL_METRIC_LABELS } from '@/constants/financial'
import { formatAmount, formatPercent } from '@/utils/formatters'

const CHART_HEIGHT = 180

const BG_COLOR = '#14161c'
const TEXT_COLOR = '#d1d4dc'
const GRID_COLOR = '#23262e'

const COLORS = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de']

interface FinancialTrendChartsProps {
  history: FinancialHealth[]
}

function buildBaseOption(title: string): EChartsOption {
  return {
    backgroundColor: BG_COLOR,
    title: {
      text: title,
      left: 8,
      top: 4,
      textStyle: { color: TEXT_COLOR, fontSize: 12, fontWeight: 'normal' },
    },
    grid: { left: 48, right: 16, top: 36, bottom: 24 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: BG_COLOR,
      borderColor: GRID_COLOR,
      textStyle: { color: TEXT_COLOR, fontSize: 11 },
    },
    textStyle: { color: TEXT_COLOR },
    xAxis: {
      type: 'category',
      axisLine: { lineStyle: { color: GRID_COLOR } },
      axisLabel: { color: TEXT_COLOR, fontSize: 10 },
      splitLine: { show: false },
    },
  }
}

export function FinancialTrendCharts({ history }: FinancialTrendChartsProps) {
  if (history.length === 0) {
    return null
  }

  const dates = history.map((item) => item.reportDate || '')
  const reportTypes = history.map((item) => item.reportType || '')

  const profitabilityOption: EChartsOption = {
    ...buildBaseOption('盈利能力趋势'),
    yAxis: {
      type: 'value',
      axisLabel: {
        color: TEXT_COLOR,
        fontSize: 10,
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
      splitLine: { lineStyle: { color: GRID_COLOR } },
    },
    series: [
      {
        name: FINANCIAL_METRIC_LABELS.roe,
        type: 'line',
        data: history.map((item) => item.metrics.roe ?? null),
        smooth: true,
        itemStyle: { color: COLORS[0] },
      },
      {
        name: FINANCIAL_METRIC_LABELS.gross_margin,
        type: 'line',
        data: history.map((item) => item.metrics.gross_margin ?? null),
        smooth: true,
        itemStyle: { color: COLORS[1] },
      },
      {
        name: FINANCIAL_METRIC_LABELS.net_margin,
        type: 'line',
        data: history.map((item) => item.metrics.net_margin ?? null),
        smooth: true,
        itemStyle: { color: COLORS[2] },
      },
    ],
  }

  const revenueOption: EChartsOption = {
    ...buildBaseOption('营收与利润趋势'),
    tooltip: {
      trigger: 'axis',
      backgroundColor: BG_COLOR,
      borderColor: GRID_COLOR,
      textStyle: { color: TEXT_COLOR, fontSize: 11 },
      valueFormatter: (value: unknown) => formatAmount(value as number | null),
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: TEXT_COLOR,
        fontSize: 10,
        formatter: (value: number) => formatAmount(value),
      },
      splitLine: { lineStyle: { color: GRID_COLOR } },
    },
    series: [
      {
        name: '营业收入',
        type: 'bar',
        data: history.map((item) => item.financialIncomeStatement?.totalRevenue ?? null),
        itemStyle: { color: COLORS[0] },
      },
      {
        name: '营业利润',
        type: 'bar',
        data: history.map((item) => item.financialIncomeStatement?.operatingProfit ?? null),
        itemStyle: { color: COLORS[1] },
      },
      {
        name: '净利润',
        type: 'line',
        data: history.map((item) => item.financialIncomeStatement?.netProfit ?? null),
        smooth: true,
        itemStyle: { color: COLORS[3] },
      },
    ],
  }

  const solvencyOption: EChartsOption = {
    ...buildBaseOption('偿债与现金流趋势'),
    yAxis: [
      {
        type: 'value',
        axisLabel: {
          color: TEXT_COLOR,
          fontSize: 10,
          formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
        },
        splitLine: { lineStyle: { color: GRID_COLOR } },
      },
      {
        type: 'value',
        axisLabel: {
          color: TEXT_COLOR,
          fontSize: 10,
          formatter: (value: number) => value.toFixed(2),
        },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: FINANCIAL_METRIC_LABELS.debt_ratio,
        type: 'line',
        yAxisIndex: 0,
        data: history.map((item) => item.metrics.debt_ratio ?? null),
        smooth: true,
        itemStyle: { color: COLORS[3] },
      },
      {
        name: FINANCIAL_METRIC_LABELS.operating_cf_ratio,
        type: 'line',
        yAxisIndex: 0,
        data: history.map((item) => item.metrics.operating_cf_ratio ?? null),
        smooth: true,
        itemStyle: { color: COLORS[4] },
      },
      {
        name: FINANCIAL_METRIC_LABELS.current_ratio,
        type: 'line',
        yAxisIndex: 1,
        data: history.map((item) => item.metrics.current_ratio ?? null),
        smooth: true,
        itemStyle: { color: COLORS[1] },
      },
    ],
  }

  const sharedXAxis = {
    data: dates,
    axisLabel: {
      formatter: (_value: string, index: number) => {
        const date = dates[index]
        return date ? date.slice(0, 7) : ''
      },
    },
  }

  const options = [profitabilityOption, revenueOption, solvencyOption]
  options.forEach((option) => {
    option.xAxis = { ...(option.xAxis as object), ...sharedXAxis }
    option.tooltip = {
      ...(option.tooltip as object),
      formatter: (params: unknown) => {
        const items = params as Array<{
          axisValue: string
          dataIndex: number
          seriesName: string
          value: number | null
          color: string
        }>
        if (!items.length) return ''
        const index = items[0].dataIndex
        const date = dates[index]
        const rType = reportTypes[index]
        let html = `<div style="font-weight:500;margin-bottom:4px;">${date}${rType ? ` (${rType})` : ''}</div>`
        items.forEach((item) => {
          const value = item.value
          const isPercent = [
            FINANCIAL_METRIC_LABELS.roe,
            FINANCIAL_METRIC_LABELS.gross_margin,
            FINANCIAL_METRIC_LABELS.net_margin,
            FINANCIAL_METRIC_LABELS.debt_ratio,
            FINANCIAL_METRIC_LABELS.operating_cf_ratio,
          ].includes(item.seriesName)
          const display = value == null
            ? '-'
            : isPercent
              ? formatPercent(value)
              : ['营业收入', '营业利润', '净利润'].includes(item.seriesName)
                ? formatAmount(value)
                : value.toFixed(2)
          html += `<div style="display:flex;align-items:center;gap:6px;">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${item.color}"></span>
            <span>${item.seriesName}: ${display}</span>
          </div>`
        })
        return html
      },
    }
  })

  return (
    <div className="space-y-3">
      {options.map((option, index) => (
        <ReactECharts
          key={index}
          option={option}
          style={{ height: `${CHART_HEIGHT}px`, width: '100%' }}
          opts={{ renderer: 'canvas' }}
        />
      ))}
    </div>
  )
}
