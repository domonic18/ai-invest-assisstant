import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { Card, Empty } from 'antd'

import type { ApiPaperTradeNavPoint } from '@ai-invest/shared'

import { ChartColors } from '@/theme/colors'
import { riseHex } from '@/utils/formatters'

interface NavChartProps {
  items: ApiPaperTradeNavPoint[]
  loading?: boolean
}

export function NavChart({ items, loading }: NavChartProps) {

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value) => (typeof value === 'number' ? value.toFixed(2) : '-'),
    },
    grid: { left: 70, right: 30, top: 20, bottom: 30 },
    xAxis: {
      type: 'category',
      data: items.map((p) => p.tradeDate),
      boundaryGap: false,
      axisLabel: {
        color: ChartColors.textMuted,
        fontSize: 10,
        formatter: (value: string) => value.slice(5),
      },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: ChartColors.panelBorder } },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: { color: ChartColors.textMuted, fontSize: 10 },
      splitLine: { lineStyle: { color: ChartColors.grid } },
    },
    series: [
      {
        name: '总资产',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        color: riseHex(),
        lineStyle: { width: 2 },
        data: items.map((p) => p.nav ?? null),
      },
    ],
  }

  return (
    <Card size="small" title={`净值曲线（最近 ${items.length} 个交易日）`} loading={loading}>
      {items.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无快照（每日盘后同步生成）" />
      ) : (
        <ReactECharts option={option} style={{ height: '280px', width: '100%' }} notMerge />
      )}
    </Card>
  )
}
