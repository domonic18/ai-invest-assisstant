import {
  BarChartOutlined,
  CloseOutlined,
  FundOutlined,
  LineChartOutlined,
} from '@ant-design/icons'
import { Button, Spin } from 'antd'
import type { EChartsOption } from 'echarts'
import ReactECharts from 'echarts-for-react'
import { useMemo, useState } from 'react'

import { IntradayChart } from '@/components/charts/IntradayChart'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useStockIntraday, useStockKline } from '@/hooks/useStocks'
import { useColorScheme } from '@/stores/settings'
import { fallHex, formatAmount, riseHex } from '@/utils/formatters'
import { calculateMACD, calculateKDJ } from '@/utils/indicators'
import { movingAverage } from '@/utils/movingAverage'
import type { IndexIntraday, StockKline, StockKlineBar } from '@ai-invest/shared'

const PERIOD_OPTIONS = [
  { label: '分时', value: 'intraday' },
  { label: '日线', value: 'daily' },
  { label: '周线', value: 'weekly' },
  { label: '月线', value: 'monthly' },
]

const MA_CONFIGS = [
  { period: 5, color: '#f59e0b' },
  { period: 10, color: '#3b82f6' },
  { period: 20, color: '#a855f7' },
  { period: 60, color: '#22c55e' },
]

const PANEL_BG = '#0c0e12'
const BORDER_COLOR = '#23262e'
const TEXT_MUTED = '#8c8c8c'
const TEXT_MAIN = '#d1d4dc'
const GRID_COLOR = '#1f2229'

export interface StockChartViewIndicators {
  volume: boolean
  ma: boolean
  macd: boolean
  kdj: boolean
}

export interface StockChartViewProps {
  code: string
  defaultPeriod?: string
  defaultIndicators?: Partial<StockChartViewIndicators>
  onRemove?: () => void
  onPeriodChange?: (period: string) => void
  onIndicatorsChange?: (indicators: StockChartViewIndicators) => void
  height?: number
  title?: string
}

interface KlineChartData {
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

function prepareKlineData(kline: StockKline): KlineChartData {
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

function buildKlineOption(
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

function adaptToIndexIntraday(stockIntraday: {
  code: string
  name: string
  tradeDate: string
  prevClose: number
  points: { time: string; price: number; volume: number; amount: number }[]
}): IndexIntraday {
  return stockIntraday as IndexIntraday
}

function IndicatorButton({
  active,
  label,
  icon,
  onClick,
}: {
  active: boolean
  label: string
  icon: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1 px-2 py-0.5 text-xs rounded transition-colors ${
        active
          ? 'bg-[#2a2e38] text-[#d1d4dc]'
          : 'text-[#8c8c8c] hover:text-[#d1d4dc] hover:bg-[#1a1d24]'
      }`}
    >
      {icon}
      {label}
    </button>
  )
}

export function StockChartView({
  code,
  defaultPeriod = 'daily',
  defaultIndicators = {},
  onRemove,
  onPeriodChange,
  onIndicatorsChange,
  height = 460,
  title,
}: StockChartViewProps) {
  useColorScheme()
  const [period, setPeriod] = useState(defaultPeriod)
  const [indicators, setIndicators] = useState<StockChartViewIndicators>({
    volume: true,
    ma: true,
    macd: false,
    kdj: false,
    ...defaultIndicators,
  })

  const handlePeriodChange = (value: string) => {
    setPeriod(value)
    onPeriodChange?.(value)
  }

  const toggleIndicator = (key: keyof StockChartViewIndicators) => {
    setIndicators((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      onIndicatorsChange?.(next)
      return next
    })
  }

  const klineParams =
    period === 'daily' || period === 'weekly' || period === 'monthly'
      ? { period: period as 'daily' | 'weekly' | 'monthly', limit: 250 }
      : { period: 'daily' as const, limit: 250 }

  const { data: klineData, isLoading: klineLoading } = useStockKline(code, klineParams)
  const { data: intradayData, isLoading: intradayLoading } = useStockIntraday(code)

  const isIntraday = period === 'intraday'

  const chartData = useMemo(() => {
    if (isIntraday || !klineData || klineData.bars.length === 0) return null
    return prepareKlineData(klineData)
  }, [klineData, isIntraday])

  const option = useMemo(() => {
    if (!chartData) return undefined
    return buildKlineOption(chartData, indicators, height)
  }, [chartData, indicators, height])

  const { chartRef, wrapperProps, onEvents } = useKlineKeyboardNav(
    chartData?.dates.length ?? 0,
  )

  const isLoading = isIntraday ? intradayLoading : klineLoading
  const hasData = isIntraday
    ? intradayData != null && intradayData.points.length > 0
    : chartData != null && chartData.bars.length > 0

  return (
    <div
      className="flex flex-col"
      style={{ backgroundColor: PANEL_BG, border: `1px solid ${BORDER_COLOR}` }}
    >
      {/* Top toolbar: period tabs + title + remove */}
      <div
        className="flex items-center justify-between px-2 py-1.5"
        style={{ borderBottom: `1px solid ${BORDER_COLOR}` }}
      >
        <div className="flex items-center gap-3">
          {title && (
            <span className="text-xs font-medium text-[#d1d4dc]">{title}</span>
          )}
          <div className="flex items-center">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => handlePeriodChange(opt.value)}
                className={`px-3 py-0.5 text-xs transition-colors ${
                  period === opt.value
                    ? 'text-[#d1d4dc] bg-[#2a2e38] rounded'
                    : 'text-[#8c8c8c] hover:text-[#d1d4dc]'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        {onRemove && (
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={onRemove}
            className="text-[#8c8c8c] hover:text-[#ff4d4f]"
          />
        )}
      </div>

      {/* Chart area */}
      <div className="relative flex-1 min-h-0">
        {isLoading ? (
          <div className="flex items-center justify-center text-[#8c8c8c]" style={{ height }}>
            <Spin size="small" />
          </div>
        ) : !hasData ? (
          <div
            className="flex items-center justify-center text-[#8c8c8c] text-sm"
            style={{ height }}
          >
            {isIntraday ? '暂无分时数据' : '暂无 K 线数据'}
          </div>
        ) : isIntraday ? (
          intradayData && (
            <IntradayChart data={adaptToIndexIntraday(intradayData)} height={height} />
          )
        ) : option ? (
          <div {...wrapperProps}>
            <ReactECharts
              ref={chartRef}
              option={option}
              style={{ height: `${height}px`, width: '100%' }}
              onEvents={onEvents}
              opts={{ renderer: 'canvas' }}
              notMerge
            />
          </div>
        ) : null}
      </div>

      {/* Bottom toolbar: indicator toggles */}
      <div
        className="flex items-center gap-1 px-2 py-1.5"
        style={{ borderTop: `1px solid ${BORDER_COLOR}` }}
      >
        <IndicatorButton
          active={indicators.volume}
          label="成交量"
          icon={<BarChartOutlined />}
          onClick={() => toggleIndicator('volume')}
        />
        <IndicatorButton
          active={indicators.ma}
          label="MA"
          icon={<LineChartOutlined />}
          onClick={() => toggleIndicator('ma')}
        />
        <IndicatorButton
          active={indicators.macd}
          label="MACD"
          icon={<FundOutlined />}
          onClick={() => toggleIndicator('macd')}
        />
        <IndicatorButton
          active={indicators.kdj}
          label="KDJ"
          icon={<LineChartOutlined />}
          onClick={() => toggleIndicator('kdj')}
        />
      </div>
    </div>
  )
}
