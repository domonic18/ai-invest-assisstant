import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'

import type { IndexIntraday } from '@ai-invest/shared'
import { useColorScheme } from '@/stores/settings'
import { fallHex, formatAmount, riseHex } from '@/utils/formatters'

interface IntradayChartProps {
  data: IndexIntraday
  height?: number
}

export function IntradayChart({ data, height = 320 }: IntradayChartProps) {
  useColorScheme()

  const points = data.points
  const times = points.map((p) => p.time)
  const prices = points.map((p) => p.price)
  const { prevClose } = data

  const up = riseHex()
  const down = fallHex()
  const lineColor = prices.length && prices[prices.length - 1] >= prevClose ? up : down

  const volumes = points.map((p, i) => ({
    value: p.volume,
    itemStyle: {
      color: i > 0 && p.price < points[i - 1].price ? down : up,
    },
  }))

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params]
        const index = (items[0] as { dataIndex?: number })?.dataIndex ?? 0
        const point = points[index]
        if (!point) return ''
        const pct = ((point.price - prevClose) / prevClose) * 100
        const pctText = `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`
        return [
          point.time,
          `价格 ${point.price.toFixed(2)} (${pctText})`,
          `成交量 ${formatAmount(point.volume)}`,
        ].join('<br/>')
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 60, right: 16, top: 12, height: '58%' },
      { left: 60, right: 16, top: '74%', height: '18%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: times,
        boundaryGap: false,
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { lineStyle: { color: '#3a3f4b' } },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: times,
        boundaryGap: false,
        axisLabel: { color: '#8c8c8c', fontSize: 10, interval: Math.ceil(times.length / 6) },
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
        name: '价格',
        type: 'line',
        data: prices,
        showSymbol: false,
        smooth: false,
        lineStyle: { color: lineColor, width: 1.5 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${lineColor}33` },
              { offset: 1, color: `${lineColor}00` },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          data: [{ yAxis: prevClose }],
          lineStyle: { color: '#8c8c8c', type: 'dashed', width: 1 },
          label: {
            color: '#8c8c8c',
            fontSize: 10,
            formatter: `昨收 ${prevClose.toFixed(2)}`,
            position: 'insideStartTop',
          },
        },
      },
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
