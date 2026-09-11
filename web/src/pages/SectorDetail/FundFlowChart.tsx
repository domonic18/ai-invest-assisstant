import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

import { useColorScheme } from '@/stores/settings'
import { formatAmount } from '@/utils/formatters'

import type { ApiSectorFundFlowPoint } from '@ai-invest/shared'

const FONT_MONO = "'SF Mono','Fira Code','Consolas',monospace"
const CUM_COLOR = '#5e6ad2'

/** 四档单型堆叠柱的身份配色（正负由柱方向表达，不占用涨跌色）。 */
const SIZE_SERIES = [
  { key: 'superLargeNet', label: '超大单', color: '#e05a4e' },
  { key: 'largeNet', label: '大单', color: '#d4a017' },
  { key: 'mediumNet', label: '中单', color: '#5b8ff9' },
  { key: 'smallNet', label: '小单', color: '#8a8f98' },
] as const

/**
 * 板块资金流向图：超大/大/中/小单净额堆叠柱（红上绿下）+
 * 主力净流入累计线（右轴），展示资金结构与持续方向。
 */
export function FundFlowChart({
  points,
  height = 190,
}: {
  points: ApiSectorFundFlowPoint[]
  height?: number
}) {
  useColorScheme()

  const dates = points.map((p) => p.tradeDate)
  let cum = 0
  const cumulative = points.map((p) => {
    cum += p.mainNetInflow ?? 0
    return Number(cum.toFixed(2))
  })

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      top: 0,
      left: 8,
      itemWidth: 10,
      itemHeight: 8,
      icon: 'rect',
      textStyle: { color: '#8c8c8c', fontSize: 10 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1a1d24',
      borderColor: '#2e323c',
      padding: [6, 8],
      textStyle: { color: '#d1d4dc' },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params]
        const index = (items[0] as { dataIndex?: number })?.dataIndex ?? 0
        const point = points[index]
        if (!point) return ''
        const row = (label: string, v: number | null, color?: string) =>
          `<div style="white-space:nowrap;font-family:${FONT_MONO};font-size:11px">` +
          `<span style="color:#5c616e">${label} </span>` +
          `<span style="${color ? `color:${color};` : ''}font-weight:600">` +
          `${v == null ? '--' : formatAmount(v)}</span></div>`
        return [
          `<div style="font-size:10px;color:#5c616e;margin-bottom:2px">${point.tradeDate}</div>`,
          ...SIZE_SERIES.map((s) => row(s.label, point[s.key] ?? null, s.color)),
          row('主力净额', point.mainNetInflow),
          row('主力累计', cumulative[index], CUM_COLOR),
        ].join('')
      },
    },
    axisPointer: { type: 'shadow' },
    grid: { left: 60, right: 56, top: 24, bottom: 22 },
    dataZoom: [{ type: 'inside' }],
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#8c8c8c', fontSize: 10, interval: Math.ceil(dates.length / 6) },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#3a3f4b' } },
    },
    yAxis: [
      {
        scale: true,
        axisLabel: {
          color: '#8c8c8c',
          fontSize: 10,
          formatter: (value: number) => formatAmount(value),
        },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      },
      {
        scale: true,
        splitLine: { show: false },
        axisLabel: {
          color: CUM_COLOR,
          fontSize: 10,
          formatter: (value: number) => formatAmount(value),
        },
      },
    ],
    series: [
      ...SIZE_SERIES.map((s) => ({
        name: s.label,
        type: 'bar' as const,
        stack: 'net',
        data: points.map((p) => p[s.key]),
        itemStyle: { color: s.color },
        barMaxWidth: 14,
      })),
      {
        name: '主力累计',
        type: 'line' as const,
        yAxisIndex: 1,
        data: cumulative,
        showSymbol: false,
        lineStyle: { color: CUM_COLOR, width: 1.5 },
      },
    ],
  }

  return (
    <ReactECharts
      option={option}
      style={{ height: `${height}px`, width: '100%' }}
      notMerge
    />
  )
}
