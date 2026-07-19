import ReactECharts from 'echarts-for-react'
import type { EChartsOption, SeriesOption } from 'echarts'

import type { IndexKlineBar } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { fallHex, formatAmount, riseHex } from '@/utils/formatters'
import { movingAverage } from '@/utils/movingAverage'

interface IndexKlineChartProps {
  bars: IndexKlineBar[]
  maWindows: number[]
  height?: number
}

const MA_COLORS = ['#f0b429', '#9d7ff5', '#3fb6e0', '#e8833a', '#c0c4d0']

export function IndexKlineChart({ bars, maWindows, height = 360 }: IndexKlineChartProps) {
  useColorScheme()

  const up = riseHex()
  const down = fallHex()

  const dates = bars.map((bar) => bar.date)
  const candles = bars.map((bar) => [bar.open, bar.close, bar.low, bar.high])
  const closes = bars.map((bar) => bar.close)
  const volumes = bars.map((bar) => ({
    value: bar.volume ?? 0,
    itemStyle: {
      color:
        bar.close != null && bar.open != null && bar.close < bar.open ? down : up,
    },
  }))

  const maSeries: SeriesOption[] = maWindows.map((window, index) => ({
    name: `MA${window}`,
    type: 'line',
    data: movingAverage(closes, window),
    showSymbol: false,
    smooth: true,
    lineStyle: { color: MA_COLORS[index % MA_COLORS.length], width: 1 },
    z: 3,
  }))

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      show: maSeries.length > 0,
      top: 0,
      textStyle: { color: '#8c8c8c', fontSize: 10 },
      itemWidth: 14,
      itemHeight: 2,
      icon: 'rect',
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params]
        const index = (items[0] as { dataIndex?: number })?.dataIndex ?? 0
        const bar = bars[index]
        if (!bar) return ''
        const lines = [
          bar.date,
          `开 ${bar.open?.toFixed(2) ?? '-'} 高 ${bar.high?.toFixed(2) ?? '-'}`,
          `低 ${bar.low?.toFixed(2) ?? '-'} 收 ${bar.close?.toFixed(2) ?? '-'}`,
          `成交量 ${formatAmount(bar.volume)}`,
        ]
        for (const item of items) {
          const series = item as { seriesName?: string; value?: number | null }
          if (series.seriesName?.startsWith('MA') && series.value != null) {
            lines.push(`${series.seriesName} ${Number(series.value).toFixed(2)}`)
          }
        }
        return lines.join('<br/>')
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 60, right: 16, top: 28, height: '56%' },
      { left: 60, right: 16, top: '74%', height: '16%' },
    ],
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }],
    xAxis: [
      {
        type: 'category',
        data: dates,
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#3a3f4b' } },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        axisLabel: { color: '#8c8c8c', fontSize: 10, interval: Math.ceil(dates.length / 6) },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#3a3f4b' } },
      },
    ],
    yAxis: [
      {
        scale: true,
        position: 'left',
        axisLabel: {
          color: '#8c8c8c',
          fontSize: 10,
          formatter: (value: number) => value.toFixed(0),
        },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
      },
      {
        gridIndex: 1,
        axisLabel: {
          color: '#8c8c8c',
          fontSize: 10,
          formatter: (value: number) => `${(value / 1e8).toFixed(1)}亿`,
        },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: candles,
        itemStyle: {
          color: up,
          color0: down,
          borderColor: up,
          borderColor0: down,
        },
      },
      ...maSeries,
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        barWidth: '60%',
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
