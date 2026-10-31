/**
 * 指数 K 线 option 构造（纯函数，IndexKlineChart 只留交互与画线宿主）。
 * 蜡烛/收盘线双形态、MA、量能副图、最新价胶囊、异动竖线、缩放窗口与可选滑块。
 */

import dayjs from 'dayjs'
import type { EChartsOption, SeriesOption } from 'echarts'

import type { IndexKlineBar, MovingAverageConfig } from '@ai-invest/shared'
import {
  fmt,
  FONT_MONO,
  lastPriceLabel,
  signed,
  WEEKDAYS,
} from '@/components/charts/chartShared'
import {
  alignedGrid,
  computePaneLayout,
  computePriceAxisRange,
  MA_LEGEND_TOP_RESERVE,
  sliderDataZoom,
} from '@/components/charts/chartLayout'
import { formatAmount } from '@/utils/formatters'
import { deriveAmplitude, deriveBarChange } from '@/utils/kline'
import { movingAverage } from '@/utils/movingAverage'

const MUTED = '#5c616e'

/** 初始可见窗口（新增缩放窗口、双击复位与数值行锚定共用）；null = 全量。 */
export interface VisibleWindow {
  startValue: number
  endValue: number
}

export function initialVisibleWindow(
  barCount: number,
  defaultVisibleBars?: number,
): VisibleWindow | null {
  if (defaultVisibleBars == null || barCount <= defaultVisibleBars) return null
  return { startValue: barCount - defaultVisibleBars, endValue: barCount - 1 }
}

export interface IndexKlineMa {
  period: number
  color: string
  values: (number | null)[]
}

export interface IndexKlineOptionInput {
  bars: IndexKlineBar[]
  maConfigs: MovingAverageConfig[]
  markers?: { date: string; label?: string }[]
  defaultVisibleBars?: number
  /** 价格/收益率小数位（债券收益率传 3，其余默认 2）。 */
  valueDecimals?: number
  /** 详情页开启底部滑块缩放；概览卡片保持 inside-only。 */
  showSlider?: boolean
  height: number
  up: string
  down: string
}

export interface IndexKlineOptionResult {
  option: EChartsOption
  /** 启用中的 MA 序列（供常驻数值行按可见窗口尾 bar 取值）。 */
  mas: IndexKlineMa[]
}

export function buildIndexKlineOption({
  bars,
  maConfigs,
  markers,
  defaultVisibleBars,
  valueDecimals = 2,
  showSlider = false,
  height,
  up,
  down,
}: IndexKlineOptionInput): IndexKlineOptionResult {
  const dates = bars.map((bar) => bar.date)
  const closes = bars.map((bar) => bar.close)
  const hasOhlc =
    bars.length > 0 &&
    bars.every((bar) => bar.open != null && bar.high != null && bar.low != null)
  const hasVolume = bars.some((bar) => (bar.volume ?? 0) > 0)
  const xAxisIndexes = hasVolume ? [0, 1] : [0]
  const win = initialVisibleWindow(bars.length, defaultVisibleBars)

  // 收益率等窄区间量级下保留必要小数，大数值刻度保持整数避免轴标签过宽
  const formatValue = (value: number) =>
    Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(valueDecimals)

  // 收盘线源（债券收益率等）无 open，量能柱按前收涨跌着色，避免恒为涨色
  const volumes = bars.map((bar, index) => {
    const { changePct } = deriveBarChange(bar, index > 0 ? bars[index - 1].close : null)
    const isDown =
      bar.open != null && bar.close != null
        ? bar.close < bar.open
        : changePct != null && changePct < 0
    return {
      value: bar.volume ?? 0,
      itemStyle: { color: isDown ? down : up },
    }
  })

  const mas: IndexKlineMa[] = maConfigs
    .filter((cfg) => cfg.enabled)
    .map((cfg) => ({
      period: cfg.period,
      color: cfg.color,
      values: movingAverage(closes, cfg.period),
    }))

  const maSeries: SeriesOption[] = mas.map((ma) => ({
    name: `MA${ma.period}`,
    type: 'line',
    data: ma.values,
    showSymbol: false,
    smooth: false,
    lineStyle: { color: ma.color, width: 1 },
    z: 3,
    yAxisIndex: 0,
  }))

  // 异动日竖线（主图 grid 内），仅渲染命中横轴的日期
  const anomalyLineData = (markers ?? [])
    .filter((m) => dates.includes(m.date))
    .map((m) => ({
      xAxis: m.date,
      lineStyle: { color: '#d4a017', type: 'dashed' as const, width: 1, opacity: 0.9 },
      label: {
        show: true,
        position: 'insideEndTop' as const,
        formatter: m.label ?? m.date,
        color: '#d4a017',
        fontSize: 9,
      },
    }))

  // 最新价胶囊（右轴端点）：蜡烛与收盘线两种形态都渲染
  const lastIdx = bars.length - 1
  const lastBar = bars[lastIdx]
  const lastPrevClose = lastIdx > 0 ? bars[lastIdx - 1].close : null
  const { changePct: lastChangePct } = lastBar
    ? deriveBarChange(lastBar, lastPrevClose)
    : { changePct: null }
  const tagColor = lastChangePct == null ? MUTED : lastChangePct >= 0 ? up : down
  const markLine = {
    silent: true,
    symbol: ['none', 'none'] as ['none', 'none'],
    lineStyle: { color: tagColor, type: 'dashed' as const, width: 1, opacity: 0.7 },
    label: lastPriceLabel(lastBar?.close, tagColor, valueDecimals),
    data: [
      ...(lastBar && lastBar.close != null ? [{ yAxis: lastBar.close }] : []),
      ...anomalyLineData,
    ],
  }

  // 主图双轴按初始可见窗口定标（缩放后由 datazoom 回调重算；收盘线由 scale 自适应）
  const initialStartIdx = win?.startValue ?? 0
  const { yMin, yMax, pctMin, pctMax } = computePriceAxisRange(
    bars,
    initialStartIdx,
    Math.max(bars.length - 1, 0),
  )

  const yAxis: EChartsOption['yAxis'] = hasOhlc
    ? [
        {
          position: 'right',
          min: yMin,
          max: yMax,
          scale: true,
          axisLabel: {
            color: '#8c8c8c',
            fontSize: 10,
            formatter: formatValue,
          },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        },
        {
          position: 'left',
          min: pctMin,
          max: pctMax,
          axisLabel: {
            fontSize: 10,
            formatter: (value: number) => {
              const v = Number(value)
              if (v > 0.005) return `{up|+${v.toFixed(1)}%}`
              if (v < -0.005) return `{down|${v.toFixed(1)}%}`
              return '{flat|0.0%}'
            },
            rich: {
              up: { color: up, fontSize: 10, fontFamily: FONT_MONO, align: 'right' },
              down: { color: down, fontSize: 10, fontFamily: FONT_MONO, align: 'right' },
              flat: { color: '#8c8c8c', fontSize: 10, fontFamily: FONT_MONO, align: 'right' },
            },
          },
          splitLine: { show: false },
        },
      ]
    : [
        {
          scale: true,
          position: 'left',
          axisLabel: {
            color: '#8c8c8c',
            fontSize: 10,
            formatter: formatValue,
          },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        },
      ]

  if (hasVolume) {
    yAxis.push({
      gridIndex: 1,
      axisLabel: {
        color: '#8c8c8c',
        fontSize: 10,
        formatter: (value: number) => formatAmount(value),
      },
      splitLine: { show: false },
    })
  }

  const layout = computePaneLayout(
    height,
    hasVolume ? 1 : 0,
    mas.length ? MA_LEGEND_TOP_RESERVE : 8,
  )
  // 右轴价格刻度 + 最新价胶囊需要右侧留白；收盘线单轴在左，右侧只留极窄边距
  const gridEdges = hasOhlc ? { left: 60, right: 64 } : { left: 60, right: 16 }
  const grids = hasVolume
    ? [alignedGrid(gridEdges, layout[0]), alignedGrid(gridEdges, layout[1])]
    : [alignedGrid(gridEdges, layout[0])]

  const dateInterval = Math.max(1, Math.ceil(dates.length / 6))
  const xAxis: EChartsOption['xAxis'] = hasVolume
    ? [
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          min: 'dataMin',
          max: 'dataMax',
          axisLabel: { show: false },
          axisTick: { show: false },
          axisLine: { lineStyle: { color: '#3a3f4b' } },
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          boundaryGap: false,
          min: 'dataMin',
          max: 'dataMax',
          axisLabel: { color: '#8c8c8c', fontSize: 10, interval: dateInterval },
          axisTick: { show: false },
          axisLine: { lineStyle: { color: '#3a3f4b' } },
        },
      ]
    : [
        {
          type: 'category',
          data: dates,
          boundaryGap: false,
          min: 'dataMin',
          max: 'dataMax',
          axisLabel: { color: '#8c8c8c', fontSize: 10, interval: dateInterval },
          axisTick: { show: false },
          axisLine: { lineStyle: { color: '#3a3f4b' } },
        },
      ]

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#1a1d24',
      borderColor: '#2e323c',
      padding: [6, 8],
      textStyle: { color: '#d1d4dc' },
      appendToBody: true,
      position: (point, _params, _dom, _rect, size) => {
        const [x, y] = point
        const { contentSize, viewSize } = size
        const px = x + 14 + contentSize[0] > viewSize[0]
          ? x - contentSize[0] - 14
          : x + 14
        const py = y - contentSize[1] - 14 < 0 ? y + 14 : y - contentSize[1] - 14
        return [px, py]
      },
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params]
        if (!items.length) return ''
        const index = (items[0] as { dataIndex?: number })?.dataIndex ?? 0
        const bar = bars[index]
        if (!bar) return ''
        const prevClose = index > 0 ? bars[index - 1].close : null
        const { change, changePct } = deriveBarChange(bar, prevClose)
        const fall =
          changePct != null
            ? changePct < 0
            : bar.open != null && bar.close != null && bar.close < bar.open
        const dirColor = fall ? down : up
        const date = dayjs(bar.date)
        const weekday = date.isValid() ? ` ${WEEKDAYS[date.day()]}` : ''

        const span = (text: string, extra = '') =>
          `<span style="font-family:${FONT_MONO};font-size:11px;${extra}">${text}</span>`
        const muted = (k: string) =>
          `<span style="font-size:11px;color:${MUTED}">${k} </span>`
        const line1 = hasOhlc
          ? muted('开') + span(fmt(bar.open, valueDecimals), 'margin-right:8px') +
            muted('高') + span(fmt(bar.high, valueDecimals), 'margin-right:8px') +
            muted('低') + span(fmt(bar.low, valueDecimals), 'margin-right:8px') +
            muted('收') + span(fmt(bar.close, valueDecimals), `font-weight:600;color:${dirColor}`)
          : muted('收') + span(fmt(bar.close, valueDecimals), `font-weight:600;color:${dirColor}`)
        const line2 =
          span(`${signed(change, valueDecimals)} (${signed(changePct)}%)`, `font-weight:600;color:${dirColor};margin-right:8px`) +
          (hasVolume ? muted('量') + span(formatAmount(bar.volume)) : '')
        const amplitudeVal = hasOhlc ? deriveAmplitude(bar, prevClose) : null
        const line3 = hasOhlc
          ? muted('振幅') + span(amplitudeVal != null ? `${amplitudeVal.toFixed(2)}%` : '--', 'margin-right:8px') +
            muted('成交额') + span(formatAmount(bar.amount))
          : ''
        const maRow = mas.length
          ? `<div style="margin-top:4px;padding-top:3px;border-top:1px solid #23262d;white-space:nowrap">${mas
              .map((ma) => {
                const v = ma.values[index]
                return `<span style="font-family:${FONT_MONO};font-size:10px;color:${ma.color};margin-right:6px">MA${ma.period} ${v == null ? '--' : v.toFixed(valueDecimals)}</span>`
              })
              .join('')}</div>`
          : ''
        return [
          `<div style="font-size:10px;color:${MUTED};margin-bottom:2px">${bar.date}${weekday}</div>`,
          `<div style="white-space:nowrap">${line1}</div>`,
          `<div style="white-space:nowrap;margin-top:2px">${line2}</div>`,
          line3 ? `<div style="white-space:nowrap;margin-top:2px">${line3}</div>` : '',
          maRow,
        ].join('')
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: grids,
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: xAxisIndexes,
        ...(win ?? {}),
      },
      ...(showSlider
        ? [sliderDataZoom(height, xAxisIndexes, win ?? { start: 0, end: 100 })]
        : []),
    ],
    xAxis,
    yAxis,
    series: [
      hasOhlc
        ? {
            name: 'K线',
            type: 'candlestick',
            data: bars.map((bar) => [bar.open, bar.close, bar.low, bar.high]),
            yAxisIndex: 0,
            itemStyle: {
              color: up,
              color0: down,
              borderColor: up,
              borderColor0: down,
            },
            markLine,
          }
        : {
            name: '收盘',
            type: 'line',
            data: closes,
            yAxisIndex: 0,
            showSymbol: false,
            lineStyle: { color: '#58a6ff', width: 1.5 },
            z: 2,
            markLine,
          },
      ...maSeries,
      ...(hasVolume
        ? [
            {
              name: '成交量',
              type: 'bar' as const,
              xAxisIndex: 1,
              yAxisIndex: hasOhlc ? 2 : 1,
              data: volumes,
              barWidth: '60%',
            },
          ]
        : []),
    ],
  }

  return { option, mas }
}
