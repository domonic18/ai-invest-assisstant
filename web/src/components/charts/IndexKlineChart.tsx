import ReactECharts from 'echarts-for-react'
import type { EChartsOption, SeriesOption } from 'echarts'

import dayjs from 'dayjs'

import type { IndexKlineBar, MovingAverageConfig } from '@ai-invest/shared'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useColorScheme } from '@/stores/settings'
import { fallHex, formatAmount, riseHex } from '@/utils/formatters'
import { deriveAmplitude, deriveBarChange } from '@/utils/kline'
import { movingAverage } from '@/utils/movingAverage'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const FONT_MONO = "'SF Mono','Fira Code','Consolas',monospace"
const MUTED = '#5c616e'

interface IndexKlineChartProps {
  bars: IndexKlineBar[]
  maConfigs: MovingAverageConfig[]
  height?: number
  defaultVisibleBars?: number
  /** 异动日竖线标注（日期须命中横轴，未命中的自动忽略）。 */
  markers?: { date: string; label?: string }[]
}

function fmt(v: number | null | undefined, decimals = 2): string {
  return v == null ? '--' : v.toFixed(decimals)
}

function signed(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '--'
  return `${v > 0 ? '+' : ''}${v.toFixed(decimals)}`
}

export function IndexKlineChart({
  bars,
  maConfigs,
  height = 360,
  defaultVisibleBars,
  markers,
}: IndexKlineChartProps) {
  useColorScheme()
  const { chartRef, wrapperProps, onEvents } = useKlineKeyboardNav(bars.length)

  const up = riseHex()
  const down = fallHex()

  const dates = bars.map((bar) => bar.date)
  const candles = bars.map((bar) => [bar.open, bar.close, bar.low, bar.high])
  const closes = bars.map((bar) => bar.close)
  // 债券收益率/利差等源仅 close（无 OHLC）→ 收盘线；无量的源隐藏量能副图
  const hasOhlc =
    bars.length > 0 &&
    bars.every((bar) => bar.open != null && bar.high != null && bar.low != null)
  const hasVolume = bars.some((bar) => (bar.volume ?? 0) > 0)
  const volumes = bars.map((bar) => ({
    value: bar.volume ?? 0,
    itemStyle: {
      color:
        bar.close != null && bar.open != null && bar.close < bar.open ? down : up,
    },
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

  const activeConfigs = maConfigs.filter((cfg) => cfg.enabled)
  const mas = activeConfigs.map((cfg) => ({
    period: cfg.period,
    color: cfg.color,
    values: movingAverage(closes, cfg.period),
  }))

// 收益率等窄区间量级下保留必要小数，避免刻度被压成整数
const formatAxisValue = (value: number) =>
  Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1)

  const maSeries: SeriesOption[] = mas.map((cfg) => ({
    name: `MA${cfg.period}`,
    type: 'line',
    data: cfg.values,
    showSymbol: false,
    smooth: true,
    lineStyle: { color: cfg.color, width: 1 },
    z: 3,
    yAxisIndex: 0,
  }))

  // 主图双轴：右轴价格、左轴涨跌幅（相对首根可见 K 线的收盘）
  const pMin = hasOhlc ? Math.min(...bars.map((b) => b.low as number)) : 0
  const pMax = hasOhlc ? Math.max(...bars.map((b) => b.high as number)) : 0
  const pad = (pMax - pMin) * 0.05 || 1
  const yMin = pMin - pad
  const yMax = pMax + pad
  const baseClose = bars[0]?.close
  const toPct = (v: number): number =>
    baseClose ? (v / baseClose - 1) * 100 : 0

  // 最新价胶囊（右轴端点）
  const lastIdx = bars.length - 1
  const lastBar = bars[lastIdx]
  const lastPrevClose = lastIdx > 0 ? bars[lastIdx - 1].close : null
  const { changePct: lastChangePct } = lastBar
    ? deriveBarChange(lastBar, lastPrevClose)
    : { changePct: null }
  const tagColor =
    lastChangePct == null ? MUTED : lastChangePct >= 0 ? up : down

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
            formatter: formatAxisValue,
          },
          splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
        },
        {
          position: 'left',
          min: toPct(yMin),
          max: toPct(yMax),
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
            formatter: formatAxisValue,
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
        formatter: (value: number) => `${(value / 1e8).toFixed(1)}亿`,
      },
      splitLine: { show: false },
    })
  }

  const option: EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      show: maSeries.length > 0,
      data: activeConfigs.map((cfg) => `MA${cfg.period}`),
      top: 0,
      textStyle: { color: '#8c8c8c', fontSize: 10 },
      itemWidth: 14,
      itemHeight: 2,
      icon: 'rect',
    },
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
          ? muted('开') + span(fmt(bar.open), 'margin-right:8px') +
            muted('高') + span(fmt(bar.high), 'margin-right:8px') +
            muted('低') + span(fmt(bar.low), 'margin-right:8px') +
            muted('收') + span(fmt(bar.close), `font-weight:600;color:${dirColor}`)
          : muted('收') + span(fmt(bar.close), `font-weight:600;color:${dirColor}`)
        const line2 =
          span(`${signed(change)} (${signed(changePct)}%)`, `font-weight:600;color:${dirColor};margin-right:8px`) +
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
                return `<span style="font-family:${FONT_MONO};font-size:10px;color:${ma.color};margin-right:6px">MA${ma.period} ${v == null ? '--' : v.toFixed(2)}</span>`
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
    grid: hasVolume
      ? [
          { left: 60, right: 16, top: 28, height: '56%' },
          { left: 60, right: 16, top: '74%', height: '16%' },
        ]
      : [{ left: 60, right: 16, top: 28, bottom: 24 }],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: hasVolume ? [0, 1] : [0],
        ...(defaultVisibleBars != null && bars.length > defaultVisibleBars
          ? { startValue: bars.length - defaultVisibleBars, endValue: bars.length - 1 }
          : {}),
      },
    ],
    xAxis: hasVolume
      ? [
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
        ]
      : [
          {
            type: 'category',
            data: dates,
            axisLabel: { color: '#8c8c8c', fontSize: 10, interval: Math.ceil(dates.length / 6) },
            axisTick: { show: false },
            axisLine: { lineStyle: { color: '#3a3f4b' } },
          },
        ],
    yAxis,
    series: [
      hasOhlc
        ? {
            name: 'K线',
            type: 'candlestick',
            data: candles,
            yAxisIndex: 0,
            itemStyle: {
              color: up,
              color0: down,
              borderColor: up,
              borderColor0: down,
            },
            markLine:
              lastBar || anomalyLineData.length
                ? {
                    silent: true,
                    symbol: ['none', 'none'],
                    lineStyle: { color: tagColor, type: 'dashed', width: 1, opacity: 0.7 },
                    label: {
                      show: true,
                      position: 'end',
                      formatter: fmt(lastBar?.close),
                      backgroundColor: tagColor,
                      color: '#fff',
                      borderRadius: 3,
                      padding: [1, 5],
                      fontSize: 10,
                      fontFamily: FONT_MONO,
                      distance: 2,
                    },
                    data: [
                      ...(lastBar && lastBar.close != null
                        ? [{ yAxis: lastBar.close }]
                        : []),
                      ...anomalyLineData,
                    ],
                  }
                : undefined,
          }
        : {
            name: '收盘',
            type: 'line',
            data: closes,
            yAxisIndex: 0,
            showSymbol: false,
            lineStyle: { color: '#58a6ff', width: 1.5 },
            z: 2,
            markLine: anomalyLineData.length
              ? {
                  silent: true,
                  symbol: ['none', 'none'],
                  data: anomalyLineData,
                }
              : undefined,
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

  return (
    <div {...wrapperProps}>
      <ReactECharts
        ref={chartRef}
        option={option}
        style={{ height: `${height}px`, width: '100%' }}
        onEvents={onEvents}
        notMerge
      />
    </div>
  )
}
