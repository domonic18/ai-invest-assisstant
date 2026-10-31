/**
 * K 线窗格布局与副图（VOL/MACD/KDJ）构建：grid/axis/series/title 逐副图产出，
 * 主装配（klineOption.ts）按 indicator 开关逐个拼装。
 */

import type { EChartsOption, SeriesOption, TitleComponentOption } from 'echarts'

import { fmt, FONT_MONO, signed } from '@/components/charts/chartShared'
import { alignedGrid } from '@/components/charts/chartLayout'
import type { PaneRect } from '@/components/charts/chartLayout'
import { fallHex, riseHex } from '@/utils/formatters'
import type { ECharts } from 'echarts'
import type { KlineChartData } from './klineData'
import { BORDER_COLOR, STOCK_GRID_EDGES, TEXT_MUTED } from './constants'

export { computePaneLayout, MA_LEGEND_TOP_RESERVE } from '@/components/charts/chartLayout'
export type { PaneRect } from '@/components/charts/chartLayout'

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

const lastNum = (arr: (number | null)[], idx: number): number | null =>
  arr.length ? (arr[Math.min(idx, arr.length - 1)] ?? null) : null

export interface SubPaneLegendRich {
  text: string
  rich?: Record<string, { color: string; fontSize: number; fontFamily: string }>
}

export const subPaneLegendId = (key: SubPaneKey): string => `legend-${key}`

/**
 * 副图图例富文本（名称 + 指定 bar 下标的值）。
 * option 构建与 datazoom 运行时刷新共用，取值锚定 idx（默认窗口尾 bar）。
 */
export function subPaneLegendTitle(
  key: SubPaneKey,
  data: KlineChartData,
  idx: number,
  up: string,
  down: string,
): SubPaneLegendRich {
  if (key === 'volume') {
    return { text: 'VOL(万手)' }
  }
  if (key === 'macd') {
    const dif = lastNum(data.macd.dif, idx)
    const dea = lastNum(data.macd.dea, idx)
    const bar = lastNum(data.macd.macd, idx)
    return {
      text: `MACD(12,26,9) {dif|DIF: ${fmt(dif)}} {dea|DEA: ${fmt(dea)}} {bar|${bar == null ? '--' : signed(bar)}}`,
      rich: {
        dif: { color: '#f0f1f5', fontSize: 11, fontFamily: FONT_MONO },
        dea: { color: '#d29922', fontSize: 11, fontFamily: FONT_MONO },
        bar: {
          color: bar != null && bar >= 0 ? up : down,
          fontSize: 11,
          fontFamily: FONT_MONO,
        },
      },
    }
  }
  const k = lastNum(data.kdj.k, idx)
  const d = lastNum(data.kdj.d, idx)
  const j = lastNum(data.kdj.j, idx)
  return {
    text: `KDJ(9,3,3) {k|K: ${fmt(k, 1)}} {d|D: ${fmt(d, 1)}} {j|J: ${fmt(j, 1)}}`,
    rich: {
      k: { color: '#f0f1f5', fontSize: 11, fontFamily: FONT_MONO },
      d: { color: '#d29922', fontSize: 11, fontFamily: FONT_MONO },
      j: { color: '#a855f7', fontSize: 11, fontFamily: FONT_MONO },
    },
  }
}

/**
 * datazoom / option 重建后按可见窗口尾 idx 刷新副图图例（title 按 id merge）。
 * option 构建时 title 固定取序列尾值，缩放到历史区间后由此校正，保证图例与图面一致。
 */
export function applySubPaneLegends(
  chart: ECharts,
  data: KlineChartData,
  keys: SubPaneKey[],
  idx: number,
): void {
  if (!keys.length) return
  const up = riseHex()
  const down = fallHex()
  chart.setOption({
    title: keys.map((key) => {
      const { text, rich } = subPaneLegendTitle(key, data, idx, up, down)
      return {
        id: subPaneLegendId(key),
        text,
        textStyle: { fontSize: 11, color: TEXT_MUTED, fontWeight: 600, rich },
      }
    }),
  } as EChartsOption)
}

/** 副图左上角图例（名称 + 最新值），配色与原型一致 */
function buildLegendTitle(
  key: SubPaneKey,
  legendTop: number,
  data: KlineChartData,
  ctx: SubPaneContext,
): TitleComponentOption {
  const { text, rich } = subPaneLegendTitle(
    key,
    data,
    data.dates.length - 1,
    ctx.up,
    ctx.down,
  )
  return {
    id: subPaneLegendId(key),
    text,
    left: 50,
    top: legendTop,
    textStyle: {
      fontSize: 11,
      color: TEXT_MUTED,
      fontWeight: 600,
      ...(rich ? { rich } : {}),
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
    grid: alignedGrid(STOCK_GRID_EDGES, pane),
    xAxis: {
      type: 'category',
      gridIndex: yAxisIndex - 1,
      data: dates,
      // 与主图一致顶格布局（默认 true 会留半带宽，柱体与上方蜡烛横向错位）
      boundaryGap: false,
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
