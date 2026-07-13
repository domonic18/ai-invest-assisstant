import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

interface LineMiniChartProps {
  data: number[]
  labels?: string[]
  color?: string
  height?: number
}

export function LineMiniChart({ data, labels, color = '#5e6ad2', height = 120 }: LineMiniChartProps) {
  const option: EChartsOption = {
    backgroundColor: 'transparent',
    grid: { top: 10, right: 10, bottom: 10, left: 10 },
    xAxis: { type: 'category', data: labels, show: false },
    yAxis: { type: 'value', show: false },
    tooltip: { trigger: 'axis' },
    series: [
      {
        data,
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { color, width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${color}66` },
              { offset: 1, color: `${color}00` },
            ],
          },
        },
      },
    ],
  }

  return <ReactECharts option={option} style={{ height: `${height}px`, width: '100%' }} />
}
