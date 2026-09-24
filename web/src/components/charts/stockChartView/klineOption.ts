/**
 * K 线 option 主装配：主图（蜡烛/MA/最新价胶囊/事件竖线）+ 副图拼装 + tooltip + dataZoom。
 * 数据准备见 klineData.ts，窗格布局与副图构建见 klinePanes.ts。
 */

import type { EChartsOption, TitleComponentOption } from 'echarts'

import dayjs from 'dayjs'

import { fmt, FONT_MONO, lastPriceLabel, signed, WEEKDAYS } from '@/components/charts/chartShared'
import { fallHex, riseHex } from '@/utils/formatters'
import { deriveAmplitude, deriveBarChange, formatWanShou } from '@/utils/kline'

import type { StockChartViewIndicators } from './StockChartView'
import { BORDER_COLOR, GRID_COLOR, TEXT_MAIN, TEXT_MUTED } from './constants'
import type { KlineChartData } from './klineData'
import { buildSubPane, computePaneLayout } from './klinePanes'
import type { KlineTradeMark } from './tradeMarkers'

const ACCENT = '#5e6ad2'
const ACCENT_SOFT = 'rgba(94,106,210,0.18)'

/** 默认缩放窗口（dataZoom start:50 / end:100），与 option 中两条 dataZoom 一致。 */
export const DEFAULT_ZOOM_START = 50
export const DEFAULT_ZOOM_END = 100

export interface PriceAxisRange {
  yMin: number
  yMax: number
  pctMin: number
  pctMax: number
}

/** computePriceAxisRange 所需的最小 bar 形状（个股/指数 K 线共用）。 */
export interface PriceRangeBar {
  low: number | null
  high: number | null
  close: number | null
}

/**
 * 按可见窗口 [startIdx, endIdx] 计算主图右轴（价格）与左轴（相对首根收盘的涨跌幅）范围。
 * 键盘/滑块缩放后由 datazoom 事件重算，使纵轴随可见区间自适应（对齐同花顺行为）。
 */
export function computePriceAxisRange(
  bars: PriceRangeBar[],
  startIdx: number,
  endIdx: number,
): PriceAxisRange {
  const slice = bars.slice(startIdx, endIdx + 1)
  const lows = slice.map((b) => b.low).filter((v): v is number => v != null)
  const highs = slice.map((b) => b.high).filter((v): v is number => v != null)
  const pMin = lows.length > 0 ? Math.min(...lows) : 0
  const pMax = highs.length > 0 ? Math.max(...highs) : 0
  const pad = (pMax - pMin) * 0.05 || 1
  const yMin = pMin - pad
  const yMax = pMax + pad
  const baseClose = bars[0]?.close
  const toPct = (v: number): number =>
    baseClose ? (v / baseClose - 1) * 100 : 0
  return { yMin, yMax, pctMin: toPct(yMin), pctMax: toPct(yMax) }
}

function pctLabel(v: number): string {
  if (v > 0.005) return `{up|+${v.toFixed(1)}%}`
  if (v < -0.005) return `{down|${v.toFixed(1)}%}`
  return '{flat|0.0%}'
}

export function buildKlineOption(
  data: KlineChartData,
  indicators: StockChartViewIndicators,
  height: number,
  markers?: { date: string; label?: string }[],
  tradeMarks?: KlineTradeMark[],
): EChartsOption {
  const upColor = riseHex()
  const downColor = fallHex()
  const { dates, bars, mas } = data

  const subPanes = [
    indicators.volume,
    indicators.macd,
    indicators.kdj,
  ].filter(Boolean).length
  const layout = computePaneLayout(height, subPanes)

  const grids: EChartsOption['grid'] = []
  const xAxes: EChartsOption['xAxis'] = []
  const yAxes: EChartsOption['yAxis'] = []
  const series: EChartsOption['series'] = []
  const titles: TitleComponentOption[] = []
  // yAxis 0=主图价格(右) 1=主图涨跌幅(左)，随后每个副图一根

  // 主图
  grids.push({ left: 46, right: 60, top: layout[0].top, height: layout[0].height })
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

  // 右轴价格：按默认缩放窗口（后 50%）可见区间定标，缩放后由 datazoom 事件重算
  const initStartIdx = Math.floor(
    ((bars.length - 1) * DEFAULT_ZOOM_START) / 100,
  )
  const { yMin, yMax, pctMin, pctMax } = computePriceAxisRange(
    bars,
    initStartIdx,
    bars.length - 1,
  )

  yAxes.push({
    position: 'right',
    min: yMin,
    max: yMax,
    axisLabel: { color: TEXT_MUTED, fontSize: 10 },
    splitLine: { lineStyle: { color: GRID_COLOR } },
    axisLine: { show: false },
  })
  yAxes.push({
    position: 'left',
    min: pctMin,
    max: pctMax,
    axisLabel: {
      fontSize: 10,
      formatter: (v: number) => pctLabel(Number(v)),
      rich: {
        up: { color: riseHex(), fontSize: 10, fontFamily: FONT_MONO, align: 'right' },
        down: { color: fallHex(), fontSize: 10, fontFamily: FONT_MONO, align: 'right' },
        flat: { color: TEXT_MUTED, fontSize: 10, fontFamily: FONT_MONO, align: 'right' },
      },
    },
    splitLine: { show: false },
    axisLine: { show: false },
  })

  // 最新价胶囊（右轴端点）+ 事件日竖线标注（仅渲染命中横轴的日期）
  const lastIdx = bars.length - 1
  const lastBar = bars[lastIdx]
  const lastPrevClose = lastIdx > 0 ? bars[lastIdx - 1].close : null
  const { changePct: lastChangePct } = deriveBarChange(lastBar, lastPrevClose)
  const tagColor =
    lastChangePct == null ? TEXT_MUTED : lastChangePct >= 0 ? upColor : downColor

  const anomalyLineData = (markers ?? [])
    .filter((m) => data.dates.includes(m.date))
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

  series.push({
    name: 'K线',
    type: 'candlestick',
    data: bars.map((b) => [b.open, b.close, b.low, b.high]),
    itemStyle: {
      color: upColor,
      color0: downColor,
      borderColor: upColor,
      borderColor0: downColor,
    },
    markLine: {
      silent: true,
      symbol: ['none', 'none'],
      lineStyle: { color: tagColor, type: 'dashed', width: 1, opacity: 0.7 },
      label: lastPriceLabel(lastBar?.close, tagColor),
      data: [
        ...(lastBar ? [{ yAxis: lastBar.close }] : []),
        ...anomalyLineData,
      ],
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

  // 模拟盘成交 B/S/T 字母标记：落在当日成交量加权均价处（B=买 S=卖 T=同日双向）
  const tradeMarkHits = (tradeMarks ?? []).filter((m) => data.dates.includes(m.date))
  if (tradeMarkHits.length) {
    const tradeMarkColor = { B: riseHex(), S: fallHex(), T: '#d4a017' } as const
    series.push({
      name: '模拟盘成交',
      type: 'scatter',
      silent: true,
      symbolSize: 1,
      data: tradeMarkHits.map((m) => ({
        value: [m.date, m.price],
        label: {
          show: true,
          formatter: m.label,
          color: tradeMarkColor[m.label],
          fontSize: 11,
          fontWeight: 'bold' as const,
          fontFamily: FONT_MONO,
          position: m.label === 'S' ? ('top' as const) : ('bottom' as const),
        },
      })),
    })
  }

  // 副图（VOL / MACD / KDJ），右轴显示刻度
  const subDefs = [
    { key: 'volume' as const, on: indicators.volume },
    { key: 'macd' as const, on: indicators.macd },
    { key: 'kdj' as const, on: indicators.kdj },
  ].filter((d) => d.on)

  subDefs.forEach((sub, i) => {
    const parts = buildSubPane(
      sub.key,
      layout[i + 1],
      { index: i, isLast: i === subDefs.length - 1, up: upColor, down: downColor },
      data,
    )
    titles.push(parts.title)
    grids.push(parts.grid)
    xAxes.push(parts.xAxis)
    yAxes.push(parts.yAxis)
    for (const s of parts.series) series.push(s)
  })

  return {
    backgroundColor: 'transparent',
    animation: false,
    title: titles,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#1a1d24',
      borderColor: '#2e323c',
      padding: [6, 8],
      textStyle: { color: TEXT_MAIN },
      // 挂到 body 渲染，避免被父容器 overflow 裁剪；上/右空间不足时翻转到下/左
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
        const index = (items[0] as { dataIndex?: number }).dataIndex ?? 0
        const bar = bars[index]
        if (!bar) return ''
        const prevClose = index > 0 ? bars[index - 1].close : null
        const { change, changePct } = deriveBarChange(bar, prevClose)
        const fall = (changePct ?? (bar.close < bar.open ? -1 : 1)) < 0
        const dirColor = fall ? fallHex() : riseHex()
        const date = dayjs(bar.date)
        const weekday = date.isValid() ? ` ${WEEKDAYS[date.day()]}` : ''

        const span = (text: string, extra = '') =>
          `<span style="font-family:${FONT_MONO};font-size:11px;${extra}">${text}</span>`
        const muted = (k: string) =>
          `<span style="font-size:11px;color:#5c616e">${k} </span>`
        const line1 =
          muted('开') + span(fmt(bar.open), 'margin-right:8px') +
          muted('高') + span(fmt(bar.high), 'margin-right:8px') +
          muted('低') + span(fmt(bar.low), 'margin-right:8px') +
          muted('收') + span(fmt(bar.close), `font-weight:600;color:${dirColor}`)
        const line2 =
          span(`${signed(change)} (${signed(changePct)}%)`, `font-weight:600;color:${dirColor};margin-right:8px`) +
          muted('量') + span(formatWanShou(bar.volume))
        const amplitudeVal = deriveAmplitude(bar, prevClose)
        const turnoverVal = bar.turnoverRate != null ? `${bar.turnoverRate.toFixed(2)}%` : '--'
        const line3 =
          muted('振幅') + span(amplitudeVal != null ? `${amplitudeVal.toFixed(2)}%` : '--', 'margin-right:8px') +
          muted('换手') + span(turnoverVal)
        const maRow = indicators.ma
          ? `<div style="margin-top:4px;padding-top:3px;border-top:1px solid #23262d;white-space:nowrap">${mas
              .map((ma) => {
                const v = ma.values[index]
                return `<span style="font-family:${FONT_MONO};font-size:10px;color:${ma.color};margin-right:6px">MA${ma.period} ${v == null ? '--' : v.toFixed(2)}</span>`
              })
              .join('')}</div>`
          : ''
        return [
          `<div style="font-size:10px;color:#5c616e;margin-bottom:2px">${bar.date}${weekday}</div>`,
          `<div style="white-space:nowrap">${line1}</div>`,
          `<div style="white-space:nowrap;margin-top:2px">${line2}</div>`,
          `<div style="white-space:nowrap;margin-top:2px">${line3}</div>`,
          maRow,
        ].join('')
      },
    },
    axisPointer: { link: xAxes.map((_, i) => ({ xAxisIndex: [i] })) },
    grid: grids,
    xAxis: xAxes,
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside', xAxisIndex: xAxes.map((_, i) => i), start: DEFAULT_ZOOM_START, end: DEFAULT_ZOOM_END },
      {
        show: true,
        xAxisIndex: xAxes.map((_, i) => i),
        type: 'slider',
        top: height - 28,
        start: DEFAULT_ZOOM_START,
        end: DEFAULT_ZOOM_END,
        height: 20,
        borderColor: BORDER_COLOR,
        backgroundColor: 'transparent',
        fillerColor: ACCENT_SOFT,
        handleIcon:
          'path://M0,0h2v18h-2z M5,0h2v18h-2z M10,0h2v18h-2z',
        handleSize: '65%',
        handleStyle: { color: '#2e323c', borderColor: 'transparent' },
        moveHandleStyle: { color: ACCENT, opacity: 0.5 },
        dataBackground: {
          lineStyle: { color: 'rgba(140,143,152,0.35)', width: 0.5 },
          areaStyle: { color: 'rgba(140,143,152,0.12)' },
        },
        selectedDataBackground: {
          lineStyle: { color: ACCENT, width: 0.8 },
          areaStyle: { color: 'rgba(94,106,210,0.10)' },
        },
        textStyle: { color: TEXT_MUTED, fontSize: 9, fontFamily: FONT_MONO },
      },
    ],
    series,
  }
}
