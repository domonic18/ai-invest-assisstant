/**
 * 画线几何纯函数：数据↔像素换算辅助、射线延伸、裁剪。
 * 全部无副作用、不依赖 ECharts 实例（convertToPixel/convertFromPixel 在 hook 层调用后传入）。
 */

import type { GridRect, KlineDrawingAnchor, KlineDrawingDirection, Point } from './types'

/** bar 日期 → 精确下标（category x 轴的 O(1) 对齐表） */
export function buildDateIndex(dates: string[]): Map<string, number> {
  const map = new Map<string, number>()
  for (let i = 0; i < dates.length; i += 1) map.set(dates[i], i)
  return map
}

/**
 * 锚点 date 对齐到「≤ 该日期的最后一根 bar」下标（越界裁剪）。
 * dates 为 YYYY-MM-DD 升序字符串，可字典序二分；空序列返回 -1。
 */
export function alignAnchorIndex(date: string, dates: string[]): number {
  if (dates.length === 0) return -1
  if (!date) return dates.length - 1
  let lo = 0
  let hi = dates.length - 1
  let ans = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (dates[mid] <= date) {
      ans = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return ans >= 0 ? ans : 0
}

/** 锚点 date → category 下标（先精确命中，再 ≤ 对齐），越界锚点吸附到绘图区边缘 bar */
export function anchorToIndex(anchor: KlineDrawingAnchor, dates: string[]): number {
  if (!anchor.date) return dates.length - 1
  const exact = buildDateIndex(dates).get(anchor.date)
  if (exact != null) return exact
  return alignAnchorIndex(anchor.date, dates)
}

/** 价格吸附到分位精度（2 位小数），避免拖拽产生无限小数落库 */
export function roundPrice(price: number): number {
  return Math.round(price * 100) / 100
}

/** 二维线段裁剪（Liang-Barsky）：与 grid 矩形求可见段，完全在外返回 null */
export function clipSegment(
  p1: Point,
  p2: Point,
  grid: GridRect,
): [Point, Point] | null {
  const dx = p2.x - p1.x
  const dy = p2.y - p1.y
  let t0 = 0
  let t1 = 1
  const checks: [number, number][] = [
    [-dx, p1.x - grid.x],
    [dx, grid.x + grid.width - p1.x],
    [-dy, p1.y - grid.y],
    [dy, grid.y + grid.height - p1.y],
  ]
  for (const [p, q] of checks) {
    if (p === 0) {
      if (q < 0) return null
    } else {
      const r = q / p
      if (p < 0) {
        if (r > t1) return null
        if (r > t0) t0 = r
      } else {
        if (r < t0) return null
        if (r < t1) t1 = r
      }
    }
  }
  return [
    { x: p1.x + t0 * dx, y: p1.y + t0 * dy },
    { x: p1.x + t1 * dx, y: p1.y + t1 * dy },
  ]
}

/** 矩形与 grid 求交（box 裁剪），完全在外返回 null */
export function clipRect(
  a: Point,
  b: Point,
  grid: GridRect,
): { x: number; y: number; width: number; height: number } | null {
  const x1 = Math.min(a.x, b.x)
  const x2 = Math.max(a.x, b.x)
  const y1 = Math.min(a.y, b.y)
  const y2 = Math.max(a.y, b.y)
  const x = Math.max(x1, grid.x)
  const y = Math.max(y1, grid.y)
  const right = Math.min(x2, grid.x + grid.width)
  const bottom = Math.min(y2, grid.y + grid.height)
  if (right <= x || bottom <= y) return null
  return { x, y, width: right - x, height: bottom - y }
}

/**
 * 射线延伸：以 a→b 定方向，按 direction 延伸至 grid 对应边缘（垂直射线延伸至上下缘）。
 * 返回绘制线段两端点（已含原始锚点线段）。
 */
export function extendRay(
  a: Point,
  b: Point,
  grid: GridRect,
  direction: KlineDrawingDirection = 'right',
): [Point, Point] {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const xMin = grid.x
  const xMax = grid.x + grid.width
  const yMin = grid.y
  const yMax = grid.y + grid.height

  if (Math.abs(dx) < 1e-6) {
    // 垂直射线：延伸至上下缘
    return [
      { x: a.x, y: direction === 'right' ? a.y : yMin },
      { x: a.x, y: direction === 'left' ? a.y : yMax },
    ]
  }

  const pointAt = (x: number): Point => ({
    x,
    y: a.y + ((x - a.x) / dx) * dy,
  })

  let start = a
  let end = b
  if (direction === 'right' || direction === 'both') {
    end = dx > 0 ? pointAt(xMax) : pointAt(xMin)
  }
  if (direction === 'left' || direction === 'both') {
    start = dx > 0 ? pointAt(xMin) : pointAt(xMax)
  }
  return [start, end]
}

/** 线型 → SVG stroke-dasharray（与原型一致：dashed 7 5 / dotted 2 5） */
export function lineDashArray(style: 'solid' | 'dashed' | 'dotted'): number[] {
  if (style === 'dashed') return [7, 5]
  if (style === 'dotted') return [2, 5]
  return []
}
