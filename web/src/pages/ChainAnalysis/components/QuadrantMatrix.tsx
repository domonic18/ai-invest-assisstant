import ReactECharts from 'echarts-for-react'

import type { ChainNode } from '@ai-invest/shared'

interface QuadrantMatrixProps {
  nodes: ChainNode[]
}

const TYPE_COLORS: Record<ChainNode['type'], string> = {
  upstream: '#58a6ff',
  midstream: '#5e6ad2',
  downstream: '#2ea043',
}

const TYPE_LABELS: Record<ChainNode['type'], string> = {
  upstream: '上游',
  midstream: '中游',
  downstream: '下游',
}

export function QuadrantMatrix({ nodes }: QuadrantMatrixProps) {
  const points = nodes.filter(
    (node) => node.localizationRate !== null && node.avgGrossMargin !== null
  )

  if (points.length === 0) {
    return null
  }

  const meanMargin =
    points.reduce((acc, node) => acc + (node.avgGrossMargin ?? 0), 0) / points.length

  const series = (Object.keys(TYPE_COLORS) as Array<ChainNode['type']>)
    .map((type) => ({
      name: TYPE_LABELS[type],
      type: 'scatter' as const,
      symbolSize: 16,
      itemStyle: { color: TYPE_COLORS[type] },
      data: points
        .filter((node) => node.type === type)
        .map((node) => ({
          name: node.name,
          value: [node.localizationRate, node.avgGrossMargin],
        })),
    }))
    .filter((item) => item.data.length > 0)

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      top: 0,
      textStyle: { color: '#8c8c8c', fontSize: 10 },
    },
    grid: { left: 50, right: 30, top: 30, bottom: 40 },
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: {
        name: string
        value: [number, number]
      }) =>
        `${params.name}<br/>国产化率：${params.value[0]}%<br/>平均毛利率：${params.value[1]}%`,
    },
    xAxis: {
      type: 'value' as const,
      name: '国产化率 %',
      nameTextStyle: { color: '#8c8c8c', fontSize: 10 },
      min: 0,
      max: 100,
      axisLabel: { color: '#8c8c8c', fontSize: 10 },
      axisLine: { lineStyle: { color: '#3a3f4b' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    },
    yAxis: {
      type: 'value' as const,
      name: '毛利率 %',
      nameTextStyle: { color: '#8c8c8c', fontSize: 10 },
      axisLabel: { color: '#8c8c8c', fontSize: 10 },
      axisLine: { lineStyle: { color: '#3a3f4b' } },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    },
    series: series.map((item, index) =>
      index === 0
        ? {
            ...item,
            markLine: {
              silent: true,
              symbol: 'none',
              lineStyle: { color: '#8c8c8c', type: 'dashed' as const },
              label: { show: false },
              data: [
                { xAxis: 50 },
                { yAxis: Number(meanMargin.toFixed(2)) },
              ],
            },
          }
        : item
    ),
  }

  return <ReactECharts option={option} style={{ height: 300 }} />
}
