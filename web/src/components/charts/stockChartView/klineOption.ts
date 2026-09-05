import type { EChartsOption, TitleComponentOption } from 'echarts'

import dayjs from 'dayjs'

import { fallHex, riseHex } from '@/utils/formatters'
import { calculateMACD, calculateKDJ } from '@/utils/indicators'
import { deriveAmplitude, deriveBarChange, formatWanShou } from '@/utils/kline'
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

const ACCENT = '#5e6ad2'
const ACCENT_SOFT = 'rgba(94,106,210,0.18)'
const FONT_MONO = "'SF Mono','Fira Code','Consolas',monospace"
const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

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

interface PaneRect {
  top: number
  height: number
}

/** 按总高与副图数分配窗格：1 副 64/36，2 副 52/24/24，3 副 52/24/24。 */
function computePaneLayout(height: number, subCount: number): PaneRect[] {
  const topReserve = 8
  const bottomReserve = 34
  const gap = 6
  const usable = Math.max(height - topReserve - bottomReserve - gap * subCount, 120)
  const ratios =
    subCount === 0
      ? [1]
      : subCount === 1
        ? [0.64, 0.36]
        : subCount === 2
          ? [0.52, 0.24, 0.24]
          : [0.52, 0.24, 0.24]
  const panes: PaneRect[] = []
  let cursor = topReserve
  for (const ratio of ratios) {
    const h = Math.round(usable * ratio)
    panes.push({ top: cursor, height: h })
    cursor += h + gap
  }
  return panes
}

function fmt(v: number | null | undefined, decimals = 2): string {
  return v == null ? '--' : v.toFixed(decimals)
}

function signed(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '--'
  return `${v > 0 ? '+' : ''}${v.toFixed(decimals)}`
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
  // yAxis 0=主图价格(右) 1=主图涨跌幅(左)，随后每个副图一根
  const subYAxisStart = 2

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

  // 右轴价格：区间随数据显式固定，供左轴涨跌幅同比例映射
  const pMin = Math.min(...data.lows)
  const pMax = Math.max(...data.highs)
  const pad = (pMax - pMin) * 0.05 || 1
  const yMin = pMin - pad
  const yMax = pMax + pad
  const baseClose = bars[0]?.close
  const toPct = (v: number): number =>
    baseClose ? (v / baseClose - 1) * 100 : 0

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
    min: toPct(yMin),
    max: toPct(yMax),
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

  // 最新价胶囊（右轴端点）
  const lastIdx = bars.length - 1
  const lastBar = bars[lastIdx]
  const lastPrevClose = lastIdx > 0 ? bars[lastIdx - 1].close : null
  const { changePct: lastChangePct } = deriveBarChange(lastBar, lastPrevClose)
  const tagColor =
    lastChangePct == null ? TEXT_MUTED : lastChangePct >= 0 ? upColor : downColor

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
      data: lastBar ? [{ yAxis: lastBar.close }] : [],
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

  // 副图（VOL / MACD / KDJ），右轴显示刻度
  const subDefs = [
    { key: 'volume' as const, on: indicators.volume },
    { key: 'macd' as const, on: indicators.macd },
    { key: 'kdj' as const, on: indicators.kdj },
  ].filter((d) => d.on)

  // 副图左上角图例（名称 + 最新值），配色与原型一致
  const lastNum = (arr: (number | null)[]): number | null =>
    arr.length ? arr[arr.length - 1] : null
  const fmtNum = (v: number | null, decimals = 2): string =>
    v == null ? '--' : v.toFixed(decimals)
  const titles: TitleComponentOption[] = []

  subDefs.forEach((sub, i) => {
    const pane = layout[i + 1]
    const isLast = i === subDefs.length - 1
    const yAxisIndex = subYAxisStart + i
    const legendTop = pane.top + 2
    if (sub.key === 'volume') {
      titles.push({
        text: 'VOL(万手)',
        left: 50,
        top: legendTop,
        textStyle: { fontSize: 11, color: TEXT_MUTED, fontWeight: 600 },
      })
    } else if (sub.key === 'macd') {
      const dif = lastNum(data.macd.dif)
      const dea = lastNum(data.macd.dea)
      const bar = lastNum(data.macd.macd)
      titles.push({
        left: 50,
        top: legendTop,
        text: `MACD(12,26,9) {dif|DIF: ${fmtNum(dif)}} {dea|DEA: ${fmtNum(dea)}} {bar|${bar == null ? '--' : signed(bar)}}`,
        textStyle: {
          fontSize: 11,
          color: TEXT_MUTED,
          fontWeight: 600,
          rich: {
            dif: { color: '#f0f1f5', fontSize: 11, fontFamily: FONT_MONO },
            dea: { color: '#d29922', fontSize: 11, fontFamily: FONT_MONO },
            bar: {
              color: bar != null && bar >= 0 ? upColor : downColor,
              fontSize: 11,
              fontFamily: FONT_MONO,
            },
          },
        },
      })
    } else {
      const k = lastNum(data.kdj.k)
      const d = lastNum(data.kdj.d)
      const j = lastNum(data.kdj.j)
      titles.push({
        left: 50,
        top: legendTop,
        text: `KDJ(9,3,3) {k|K: ${fmtNum(k, 1)}} {d|D: ${fmtNum(d, 1)}} {j|J: ${fmtNum(j, 1)}}`,
        textStyle: {
          fontSize: 11,
          color: TEXT_MUTED,
          fontWeight: 600,
          rich: {
            k: { color: '#f0f1f5', fontSize: 11, fontFamily: FONT_MONO },
            d: { color: '#d29922', fontSize: 11, fontFamily: FONT_MONO },
            j: { color: '#a855f7', fontSize: 11, fontFamily: FONT_MONO },
          },
        },
      })
    }
    grids.push({ left: 46, right: 60, top: pane.top, height: pane.height })
    xAxes.push({
      type: 'category',
      gridIndex: yAxisIndex - 1,
      data: dates,
      axisLabel: isLast
        ? {
            show: true,
            color: TEXT_MUTED,
            fontSize: 10,
            interval: Math.floor(dates.length / 6),
          }
        : { show: false },
      axisTick: { show: false },
      axisLine: isLast ? { lineStyle: { color: BORDER_COLOR } } : { show: false },
    })
    yAxes.push({
      gridIndex: yAxisIndex - 1,
      axisLabel:
        sub.key === 'volume'
          ? {
              show: true,
              color: TEXT_MUTED,
              fontSize: 9,
              formatter: (v: number) => (Number(v) === 0 ? '0' : `${(Number(v) / 1e6).toFixed(0)}`),
            }
          : {
              show: true,
              color: TEXT_MUTED,
              fontSize: 9,
              formatter: (v: number) => Number(v).toFixed(sub.key === 'kdj' ? 1 : 2),
            },
      splitLine: { show: false },
      axisLine: { show: false },
    })

    if (sub.key === 'volume') {
      series.push({
        name: '成交量',
        type: 'bar',
        xAxisIndex: yAxisIndex - 1,
        yAxisIndex,
        data: data.volumes.map((v, idx) => ({
          value: v,
          itemStyle: { color: data.closes[idx] >= data.opens[idx] ? upColor : downColor },
        })),
      })
    } else if (sub.key === 'macd') {
      series.push(
        {
          name: 'MACD',
          type: 'bar',
          xAxisIndex: yAxisIndex - 1,
          yAxisIndex,
          data: data.macd.macd.map((v) => ({
            value: v,
            itemStyle: { color: v != null && v >= 0 ? upColor : downColor },
          })),
          markLine: {
            silent: true,
            symbol: 'none',
            label: { show: false },
            lineStyle: { color: '#2e323c', type: 'dashed', width: 1 },
            data: [{ yAxis: 0 }],
          },
        },
        {
          name: 'DIF',
          type: 'line',
          xAxisIndex: yAxisIndex - 1,
          yAxisIndex,
          data: data.macd.dif,
          showSymbol: false,
          lineStyle: { color: '#f0f1f5', width: 1 },
        },
        {
          name: 'DEA',
          type: 'line',
          xAxisIndex: yAxisIndex - 1,
          yAxisIndex,
          data: data.macd.dea,
          showSymbol: false,
          lineStyle: { color: '#d29922', width: 1 },
        },
      )
    } else {
      series.push(
        {
          name: 'K',
          type: 'line',
          xAxisIndex: yAxisIndex - 1,
          yAxisIndex,
          data: data.kdj.k,
          showSymbol: false,
          lineStyle: { color: '#f0f1f5', width: 1 },
        },
        {
          name: 'D',
          type: 'line',
          xAxisIndex: yAxisIndex - 1,
          yAxisIndex,
          data: data.kdj.d,
          showSymbol: false,
          lineStyle: { color: '#d29922', width: 1 },
        },
        {
          name: 'J',
          type: 'line',
          xAxisIndex: yAxisIndex - 1,
          yAxisIndex,
          data: data.kdj.j,
          showSymbol: false,
          lineStyle: { color: '#a855f7', width: 1 },
        },
      )
    }
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
      { type: 'inside', xAxisIndex: xAxes.map((_, i) => i), start: 50, end: 100 },
      {
        show: true,
        xAxisIndex: xAxes.map((_, i) => i),
        type: 'slider',
        top: height - 28,
        start: 50,
        end: 100,
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
