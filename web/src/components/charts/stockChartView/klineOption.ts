import type { EChartsOption } from 'echarts'

import { fallHex, formatAmount, riseHex } from '@/utils/formatters'
import { calculateMACD, calculateKDJ } from '@/utils/indicators'
import { movingAverage } from '@/utils/movingAverage'
import type { StockKline, StockKlineBar } from '@ai-invest/shared'

import type { StockChartViewIndicators } from './StockChartView'
import {
  BORDER_COLOR,
  GRID_COLOR,
  MA_CONFIGS,
  TEXT_MAIN,
  TEXT_MUTED,
} from './constants'

export interface KlineChartData {
  dates: string[]
  bars: StockKlineBar[]
  opens: number[]
  closes: number[]
  highs: number[]
  lows: number[]
  volumes: number[]
  mas: { period: number; color: string; values: (number | null)[] }[]
  macd: ReturnType<typeof calculateMACD>
  kdj: ReturnType<typeof calculateKDJ>
}

export function prepareKlineData(kline: StockKline): KlineChartData {
  const bars = kline.bars
  const dates = bars.map((b) => b.date)
  const opens = bars.map((b) => b.open)
  const closes = bars.map((b) => b.close)
  const highs = bars.map((b) => b.high)
  const lows = bars.map((b) => b.low)
  const volumes = bars.map((b) => b.volume)

  const mas = MA_CONFIGS.map((cfg) => ({
    ...cfg,
    values: movingAverage(closes, cfg.period),
  }))

  return {
    dates,
    bars,
    opens,
    closes,
    highs,
    lows,
    volumes,
    mas,
    macd: calculateMACD(closes),
    kdj: calculateKDJ(highs, lows, closes),
  }
}

export function buildKlineOption(
  data: KlineChartData,
  indicators: StockChartViewIndicators,
  height: number,
): EChartsOption {
  const upColor = riseHex()
  const downColor = fallHex()
  const { dates, volumes, mas, macd, kdj } = data

  const grids: EChartsOption['grid'] = []
  const xAxes: EChartsOption['xAxis'] = []
  const yAxes: EChartsOption['yAxis'] = []
  const series: EChartsOption['series'] = []

  let currentTop = 8
  const gap = 8

  const mainHeight = indicators.volume || indicators.macd || indicators.kdj ? '48%' : '85%'
  grids.push({
    left: 56,
    right: 12,
    top: currentTop,
    height: mainHeight,
  })
  xAxes.push({
    type: 'category',
    data: dates,
    boundaryGap: false,
    axisLine: { onZero: false, lineStyle: { color: BORDER_COLOR } },
    axisLabel: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
    min: 'dataMin',
    max: 'dataMax',
  })
  yAxes.push({
    scale: true,
    position: 'right',
    axisLabel: { color: TEXT_MUTED, fontSize: 10 },
    splitLine: { lineStyle: { color: GRID_COLOR } },
  })
  series.push({
    name: 'K线',
    type: 'candlestick',
    data: data.bars.map((b) => [b.open, b.close, b.low, b.high]),
    itemStyle: {
      color: upColor,
      color0: downColor,
      borderColor: upColor,
      borderColor0: downColor,
    },
  })

  if (indicators.ma) {
    for (const ma of mas) {
      series.push({
        name: `MA${ma.period}`,
        type: 'line',
        data: ma.values,
        showSymbol: false,
        smooth: false,
        lineStyle: { color: ma.color, width: 1 },
      })
    }
  }

  currentTop += parseInt(mainHeight, 10) + gap

  if (indicators.volume) {
    grids.push({
      left: 56,
      right: 12,
      top: `${currentTop}%`,
      height: '14%',
    })
    xAxes.push({
      type: 'category',
      gridIndex: grids.length - 1,
      data: dates,
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false },
    })
    yAxes.push({
      gridIndex: grids.length - 1,
      axisLabel: { show: false },
      splitLine: { show: false },
    })
    series.push({
      name: '成交量',
      type: 'bar',
      xAxisIndex: grids.length - 1,
      yAxisIndex: grids.length - 1,
      data: volumes.map((v, i) => ({
        value: v,
        itemStyle: {
          color: data.closes[i] >= data.opens[i] ? upColor : downColor,
        },
      })),
    })
    currentTop += 14 + gap
  }

  if (indicators.macd) {
    grids.push({
      left: 56,
      right: 12,
      top: `${currentTop}%`,
      height: '14%',
    })
    xAxes.push({
      type: 'category',
      gridIndex: grids.length - 1,
      data: dates,
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false },
    })
    yAxes.push({
      gridIndex: grids.length - 1,
      axisLabel: { show: false },
      splitLine: { show: false },
    })
    series.push({
      name: 'MACD',
      type: 'bar',
      xAxisIndex: grids.length - 1,
      yAxisIndex: grids.length - 1,
      data: macd.macd.map((v) => ({
        value: v,
        itemStyle: {
          color: v != null && v >= 0 ? upColor : downColor,
        },
      })),
    })
    series.push({
      name: 'DIF',
      type: 'line',
      xAxisIndex: grids.length - 1,
      yAxisIndex: grids.length - 1,
      data: macd.dif,
      showSymbol: false,
      lineStyle: { color: '#f59e0b', width: 1 },
    })
    series.push({
      name: 'DEA',
      type: 'line',
      xAxisIndex: grids.length - 1,
      yAxisIndex: grids.length - 1,
      data: macd.dea,
      showSymbol: false,
      lineStyle: { color: '#3b82f6', width: 1 },
    })
    currentTop += 14 + gap
  }

  if (indicators.kdj) {
    grids.push({
      left: 56,
      right: 12,
      top: `${currentTop}%`,
      height: '14%',
    })
    xAxes.push({
      type: 'category',
      gridIndex: grids.length - 1,
      data: dates,
      axisLabel: { color: TEXT_MUTED, fontSize: 10, interval: Math.floor(dates.length / 6) },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: BORDER_COLOR } },
    })
    yAxes.push({
      gridIndex: grids.length - 1,
      axisLabel: { show: false },
      splitLine: { show: false },
    })
    series.push({
      name: 'K',
      type: 'line',
      xAxisIndex: grids.length - 1,
      yAxisIndex: grids.length - 1,
      data: kdj.k,
      showSymbol: false,
      lineStyle: { color: '#f59e0b', width: 1 },
    })
    series.push({
      name: 'D',
      type: 'line',
      xAxisIndex: grids.length - 1,
      yAxisIndex: grids.length - 1,
      data: kdj.d,
      showSymbol: false,
      lineStyle: { color: '#3b82f6', width: 1 },
    })
    series.push({
      name: 'J',
      type: 'line',
      xAxisIndex: grids.length - 1,
      yAxisIndex: grids.length - 1,
      data: kdj.j,
      showSymbol: false,
      lineStyle: { color: '#a855f7', width: 1 },
    })
  }

  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#1a1d24',
      borderColor: BORDER_COLOR,
      textStyle: { color: TEXT_MAIN },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params]
        if (!items.length) return ''
        const index = (items[0] as { dataIndex?: number }).dataIndex ?? 0
        const date = dates[index]
        const lines = [`<strong>${date}</strong>`]
        items.forEach((p) => {
          const param = p as {
            seriesName?: string
            value?: number | number[] | { value: number }
          }
          const name = param.seriesName ?? ''
          let value = param.value
          if (typeof value === 'object' && value !== null && 'value' in value) {
            value = (value as { value: number }).value
          }
          if (Array.isArray(value)) {
            const [open, close, low, high] = value
            lines.push(`${name} 开:${open} 高:${high} 低:${low} 收:${close}`)
          } else if (value != null) {
            lines.push(`${name}: ${formatAmount(Number(value))}`)
          }
        })
        return lines.join('<br/>')
      },
    },
    axisPointer: { link: xAxes.map((_, i) => ({ xAxisIndex: [i] })) },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside', xAxisIndex: xAxes.map((_, i) => i), start: 50, end: 100 },
      {
        show: true,
        xAxisIndex: xAxes.map((_, i) => i),
        type: 'slider',
        top: height - 24,
        start: 50,
        end: 100,
        height: 16,
        borderColor: 'transparent',
        fillerColor: 'rgba(255,255,255,0.1)',
        handleStyle: { color: TEXT_MUTED },
        textStyle: { color: TEXT_MUTED },
      },
    ],
    series,
  }
}
