/**
 * K 线窗格布局与副图（VOL/MACD/KDJ）构建：grid/axis/series/title 逐副图产出，
 * 主装配（klineOption.ts）按 indicator 开关逐个拼装。
 */

import type { EChartsOption, SeriesOption, TitleComponentOption } from 'echarts'

import { fmt, FONT_MONO, signed } from '@/components/charts/chartShared'
import type { KlineChartData } from './klineData'
import { BORDER_COLOR, TEXT_MUTED } from './constants'

export interface PaneRect {
  top: number
  height: number
}

/** 按总高与副图数分配窗格：1 副 64/36，2 副 52/24/24，3 副 52/24/24。 */
export function computePaneLayout(height: number, subCount: number): PaneRect[] {
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

export type SubPaneKey = 'volume' | 'macd' | 'kdj'

type GridEntry = Extract<NonNullable<EChartsOption['grid']>, unknown[]>[number]
type XAxisEntry = Extract<NonNullable<EChartsOption['xAxis']>, unknown[]>[number]
type YAxisEntry = Extract<NonNullable<EChartsOption['yAxis']>, unknown[]>[number]

export interface SubPaneParts {
  title: TitleComponentOption
  grid: GridEntry
  xAxis: XAxisEntry
  yAxis: YAxisEntry
  series: SeriesOption[]
}

interface SubPaneContext {
  /** 副图序号（0 起）：grid/xAxis 下标 = index+1，yAxis 下标 = index+2 */
  index: number
  /** 最底一副图显示 x 轴刻度 */
  isLast: boolean
  up: string
  down: string
}

const lastNum = (arr: (number | null)[]): number | null =>
  arr.length ? arr[arr.length - 1] : null

/** 副图左上角图例（名称 + 最新值），配色与原型一致 */
function buildLegendTitle(
  key: SubPaneKey,
  legendTop: number,
  data: KlineChartData,
  ctx: SubPaneContext,
): TitleComponentOption {
  if (key === 'volume') {
    return {
      text: 'VOL(万手)',
      left: 50,
      top: legendTop,
      textStyle: { fontSize: 11, color: TEXT_MUTED, fontWeight: 600 },
    }
  }
  if (key === 'macd') {
    const dif = lastNum(data.macd.dif)
    const dea = lastNum(data.macd.dea)
    const bar = lastNum(data.macd.macd)
    return {
      left: 50,
      top: legendTop,
      text: `MACD(12,26,9) {dif|DIF: ${fmt(dif)}} {dea|DEA: ${fmt(dea)}} {bar|${bar == null ? '--' : signed(bar)}}`,
      textStyle: {
        fontSize: 11,
        color: TEXT_MUTED,
        fontWeight: 600,
        rich: {
          dif: { color: '#f0f1f5', fontSize: 11, fontFamily: FONT_MONO },
          dea: { color: '#d29922', fontSize: 11, fontFamily: FONT_MONO },
          bar: {
            color: bar != null && bar >= 0 ? ctx.up : ctx.down,
            fontSize: 11,
            fontFamily: FONT_MONO,
          },
        },
      },
    }
  }
  const k = lastNum(data.kdj.k)
  const d = lastNum(data.kdj.d)
  const j = lastNum(data.kdj.j)
  return {
    left: 50,
    top: legendTop,
    text: `KDJ(9,3,3) {k|K: ${fmt(k, 1)}} {d|D: ${fmt(d, 1)}} {j|J: ${fmt(j, 1)}}`,
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
  }
}

function buildSubSeries(
  key: SubPaneKey,
  yAxisIndex: number,
  data: KlineChartData,
  ctx: SubPaneContext,
): SeriesOption[] {
  const { up, down } = ctx
  if (key === 'volume') {
    return [
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: yAxisIndex - 1,
        yAxisIndex,
        data: data.volumes.map((v, idx) => ({
          value: v,
          itemStyle: { color: data.closes[idx] >= data.opens[idx] ? up : down },
        })),
      },
    ]
  }
  if (key === 'macd') {
    return [
      {
        name: 'MACD',
        type: 'bar',
        xAxisIndex: yAxisIndex - 1,
        yAxisIndex,
        data: data.macd.macd.map((v) => ({
          value: v,
          itemStyle: { color: v != null && v >= 0 ? up : down },
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
    ]
  }
  return [
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
  ]
}

export function buildSubPane(
  key: SubPaneKey,
  pane: PaneRect,
  ctx: SubPaneContext,
  data: KlineChartData,
): SubPaneParts {
  const yAxisIndex = ctx.index + 2
  const isLast = ctx.isLast
  const dates = data.dates
  return {
    title: buildLegendTitle(key, pane.top + 2, data, ctx),
    grid: { left: 46, right: 60, top: pane.top, height: pane.height },
    xAxis: {
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
    },
    yAxis: {
      gridIndex: yAxisIndex - 1,
      axisLabel:
        key === 'volume'
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
              formatter: (v: number) => Number(v).toFixed(key === 'kdj' ? 1 : 2),
            },
      splitLine: { show: false },
      axisLine: { show: false },
    },
    series: buildSubSeries(key, yAxisIndex, data, ctx),
  }
}
