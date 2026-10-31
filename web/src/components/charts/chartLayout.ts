/**
 * K 线族多 grid 布局契约（个股/板块/指数共用）。
 *
 * `outerBoundsMode: 'none'` 是硬约束：ECharts 6 默认 'auto' 会按各 grid 自身坐标轴
 * 标签宽度扩张/收缩绘图区（见 echarts Grid.js → layOutGridByOuterBounds），同一张图
 * 内主图与副图即使写了相同的 left/right，最终绘图区 x/width 也会不同，导致蜡烛与
 * 量能柱逐根错位。所有 grid 必须经 alignedGrid 生成并共享同一组左右边界。
 */

import type { EChartsOption } from 'echarts'

export interface PaneRect {
  top: number
  height: number
}

/** 单图内所有 grid 必须共享的左右边界。 */
export interface GridEdges {
  left: number
  right: number
}

type GridEntry = Extract<NonNullable<EChartsOption['grid']>, unknown[]>[number]
type DataZoomEntry = Extract<NonNullable<EChartsOption['dataZoom']>, unknown[]>[number]

/** MA 数值行（两行 11px）悬浮于主图内时需预留的顶部高度。 */
export const MA_LEGEND_TOP_RESERVE = 34

/** 生成对齐后的 grid：统一左右边界并关闭 outerBounds 自适应。 */
export function alignedGrid(edges: GridEdges, rect: PaneRect): GridEntry {
  return { ...edges, ...rect, outerBoundsMode: 'none' }
}

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

/** 按总高与副图数分配窗格：1 副 64/36，2 副 52/24/24，3 副 46/18/18/18。 */
export function computePaneLayout(height: number, subCount: number, topReserve = 8): PaneRect[] {
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
          : [0.46, 0.18, 0.18, 0.18]
  const panes: PaneRect[] = []
  let cursor = topReserve
  for (const ratio of ratios) {
    const h = Math.round(usable * ratio)
    panes.push({ top: cursor, height: h })
    cursor += h + gap
  }
  return panes
}

/** 底部滑块缩放条（与 inside 缩放共用窗口，样式对齐个股 K 线）。 */
export function sliderDataZoom(
  height: number,
  xAxisIndex: number[],
  range: { start?: number; end?: number; startValue?: number; endValue?: number },
): DataZoomEntry {
  return {
    show: true,
    type: 'slider',
    xAxisIndex,
    top: height - 28,
    height: 20,
    ...range,
    borderColor: '#32363f',
    backgroundColor: 'transparent',
    fillerColor: 'rgba(94,106,210,0.18)',
    handleIcon: 'path://M0,0h2v18h-2z M5,0h2v18h-2z M10,0h2v18h-2z',
    handleSize: '65%',
    handleStyle: { color: '#2e323c', borderColor: 'transparent' },
    moveHandleStyle: { color: '#5e6ad2', opacity: 0.5 },
    dataBackground: {
      lineStyle: { color: 'rgba(140,143,152,0.35)', width: 0.5 },
      areaStyle: { color: 'rgba(140,143,152,0.12)' },
    },
    selectedDataBackground: {
      lineStyle: { color: '#5e6ad2', width: 0.8 },
      areaStyle: { color: 'rgba(94,106,210,0.10)' },
    },
    textStyle: { color: '#8c8c8c', fontSize: 9, fontFamily: 'monospace' },
  }
}
