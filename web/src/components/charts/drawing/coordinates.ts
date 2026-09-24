/**
 * 画线坐标换算：数据锚点 (date, price) ↔ 像素坐标。
 * 锚点持久态只存数据坐标，像素仅在渲染/拖拽瞬间经 convertToPixel/convertFromPixel 存在。
 */

import type { ECharts } from 'echarts'

import { getMainGridRect } from './chartInternals'
import { anchorToIndex, roundPrice } from './geometry'
import type { GridRect, KlineDrawingAnchor, Point, UserKlineDrawing } from './types'

/** 数据锚点 → 像素 */
export function anchorToPx(chart: ECharts, dates: string[], a: KlineDrawingAnchor): Point {
  // 无 date 锚点（hline 契约）：x 无意义，落到绘图区水平中心（手柄/样式条定位，
  // 否则 anchorToIndex 会把空 date 对齐到最后一根 bar，钉在图表右缘）
  if (!a.date) {
    const grid = getMainGridRect(chart)
    return {
      x: (grid?.x ?? 0) + (grid?.width ?? 0) / 2,
      y: chart.convertToPixel({ yAxisIndex: 0 }, a.price),
    }
  }
  return {
    x: chart.convertToPixel({ xAxisIndex: 0 }, anchorToIndex(a, dates)),
    y: chart.convertToPixel({ yAxisIndex: 0 }, a.price),
  }
}

/** 像素 → 数据锚点；hline 只承载价格（后端契约：水平线锚点不带 date） */
export function pxToAnchor(
  chart: ECharts,
  dates: string[],
  pt: Point,
  omitDate = false,
): KlineDrawingAnchor {
  const price = roundPrice(chart.convertFromPixel({ yAxisIndex: 0 }, pt.y))
  if (omitDate || !dates.length) return { date: '', price }
  const idx = Math.round(chart.convertFromPixel({ xAxisIndex: 0 }, pt.x))
  const clamped = Math.min(Math.max(idx, 0), dates.length - 1)
  return { date: dates[clamped] ?? '', price }
}

/** 单条用户画线 → 全部锚点像素 */
export function drawingPx(chart: ECharts, dates: string[], d: UserKlineDrawing): Point[] {
  return d.anchors.map((a) => anchorToPx(chart, dates, a))
}

/** 主图 grid 矩形内判定（草稿落点/点击取消的边界） */
export function inRect(x: number, y: number, r: GridRect): boolean {
  return x >= r.x && x <= r.x + r.width && y >= r.y && y <= r.y + r.height
}
