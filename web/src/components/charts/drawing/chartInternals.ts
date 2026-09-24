/**
 * ECharts/zrender 内部 API 的单点封装：画线图层对图表私有结构的所有强转集中于此。
 * 其余模块（specs/坐标/sessions/hook）只消费本模块的安全函数，不再各自 `as unknown as`。
 */

import type { ECharts, EChartsOption } from 'echarts'

import { DRAWING_ROOT_PREFIX, type GridRect } from './types'

/** 命中元素是否属于画线图层（沿 parent 链找命名空间 id；K 线/均线等主图元素不算） */
export function isDrawingElement(target: unknown): boolean {
  let el = target as { id?: unknown; parent?: unknown } | null
  while (el) {
    if (typeof el.id === 'string' && el.id.startsWith(DRAWING_ROOT_PREFIX)) return true
    el = el.parent as typeof el
  }
  return false
}

/** 主图 grid 矩形（内部 API，取不到返回 null 降级） */
export function getMainGridRect(chart: ECharts): GridRect | null {
  try {
    const model = (
      chart as unknown as {
        getModel(): {
          getComponent(name: string, index: number): {
            axis: { grid: { getRect(): GridRect } }
          }
        }
      }
    ).getModel()
    const rect = model.getComponent('xAxis', 0).axis.grid.getRect()
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
  } catch {
    return null
  }
}

/**
 * 视图指纹：轴像素探针（首尾下标 + y 轴定点）与日期序列端点。
 * dataZoom 平移/缩放/周期切换只改变坐标系、不改变 drawings/dates.length，
 * 签名若不含指纹会短路跳过重定位，画线停留在旧像素坐标（与 K 线错位）。
 */
export function viewFingerprint(chart: ECharts, dates: string[]): string {
  try {
    const x0 = chart.convertToPixel({ xAxisIndex: 0 }, 0)
    const x1 = chart.convertToPixel({ xAxisIndex: 0 }, dates.length - 1)
    const y0 = chart.convertToPixel({ yAxisIndex: 0 }, 0)
    return `${Math.round(x0)}:${Math.round(x1)}:${Math.round(y0)}:${dates[0] ?? ''}:${dates[dates.length - 1] ?? ''}`
  } catch {
    return 'n/a'
  }
}

/** 当前 option 的 dataZoom 条目数（armed 时需全部禁用，图表可能同时配 inside+slider） */
export function dataZoomCount(chart: ECharts): number {
  try {
    const opt = chart.getOption() as { dataZoom?: unknown } | undefined
    return Array.isArray(opt?.dataZoom) ? opt.dataZoom.length : 0
  } catch {
    return 0
  }
}

/** zrender storage 内部 API：按 id 取存活元素（拖拽兄弟镜像与图层擦除探测用）；已销毁实例返回 undefined */
export function getZrEl(
  chart: ECharts,
  id: string,
): { x?: number; y?: number; dirty?: () => void } | undefined {
  const zr = chart.getZr()
  if (!zr || chart.isDisposed()) return undefined
  const storage = (
    zr as unknown as {
      storage?: { getDisplayList?: () => ({ id?: unknown; x?: number; y?: number; dirty?: () => void } | undefined)[] }
    }
  ).storage
  return storage?.getDisplayList?.().find((el) => el && el.id === id)
}

/** setOption 降级封装：失败仅告警不抛出（图层异常静默为不渲染，不冻结宿主图表），返回是否成功 */
export function safeSetOption(chart: ECharts, option: Record<string, unknown>): boolean {
  try {
    chart.setOption(option as EChartsOption)
    return true
  } catch (err) {
    console.warn('[drawing] 图层降级', err)
    return false
  }
}
