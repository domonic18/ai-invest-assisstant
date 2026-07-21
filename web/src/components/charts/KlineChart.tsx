import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

import type { KlineData } from '@ai-invest/shared'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useColorScheme } from '@/stores/settings'
import { fallHex, riseHex } from '@/utils/formatters'

interface KlineChartProps {
  data: KlineData[]
  height?: number
}

export function KlineChart({ data, height = 400 }: KlineChartProps) {
  useColorScheme()
  const { chartRef, wrapperProps, onEvents } = useKlineKeyboardNav(data.length)

  const sorted = [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
  const dates = sorted.map((item) => item.date)
  const values = sorted.map((item) => [item.open, item.close, item.low, item.high])
  const volumes = sorted.map((item) => [item.date, item.volume])

  const upColor = riseHex()
  const downColor = fallHex()

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    grid: [
      { left: '10%', right: '8%', height: '55%' },
      { left: '10%', right: '8%', top: '68%', height: '16%' },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: false, axisLine: { onZero: false }, splitLine: { show: false }, min: 'dataMin', max: 'dataMax' },
      { type: 'category', gridIndex: 1, data: dates, axisLabel: { show: false } },
    ],
    yAxis: [
      { scale: true, splitArea: { show: true, areaStyle: { color: ['rgba(255,255,255,0.02)', 'rgba(255,255,255,0.05)'] } } },
      { scale: true, gridIndex: 1, splitNumber: 2, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 50, end: 100 },
      { show: true, xAxisIndex: [0, 1], type: 'slider', top: '85%', start: 50, end: 100 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: values,
        itemStyle: {
          color: upColor,
          color0: downColor,
          borderColor: upColor,
          borderColor0: downColor,
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params: { dataIndex: number }) => {
            const index = params.dataIndex
            return sorted[index].close >= sorted[index].open ? upColor : downColor
          },
        },
      },
    ],
  }

  return (
    <div {...wrapperProps}>
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: `${height}px`, width: '100%' }}
        onEvents={onEvents}
        opts={{ renderer: 'canvas' }}
      />
    </div>
  )
}
