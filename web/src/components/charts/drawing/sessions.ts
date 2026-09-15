/**
 * 拖拽会话：zrender 原生 Draggable 的会话状态与帧更新。
 * 被抓元素由 zrender 原生 drift，兄弟元素经 storage 镜像 position；
 * 会话只记像素锚点，mouseup 时一次性回换算为数据锚点落库。
 */

import type { ECharts } from 'echarts'

import { getZrEl } from './chartInternals'
import { drawingPx, pxToAnchor } from './coordinates'
import type { AiDrawingItem, KlineDrawingAnchor, Point, UserKlineDrawing } from './types'

export interface DragSession {
  drawingId: string
  kind: 'anchor' | 'move'
  anchorIndex: number
  /** move 拖拽：需跟随被抓元素镜像 position 的兄弟元素 id（anchor 拖拽为空） */
  siblingIds: string[]
  /** 拖拽中的像素锚点（实时） */
  px: Point[]
  /** 拖拽起点像素锚点快照 */
  originPx: Point[]
  /** 拖拽起点指针位置 */
  start: Point
  /** AI 画线拖拽（label 即组内唯一键）；用户画线为空 */
  ai?: { label: string }
}

/** 无位移拖拽（纯点击）不提交更新 */
export function dragMoved(drag: DragSession): boolean {
  return drag.px.some((pt, i) => pt.x !== drag.originPx[i].x || pt.y !== drag.originPx[i].y)
}

/** 用户画线拖拽会话起点（锚点像素快照） */
export function startUserDrag(
  d: UserKlineDrawing,
  chart: ECharts,
  dates: string[],
  partial: Pick<DragSession, 'drawingId' | 'kind' | 'anchorIndex' | 'siblingIds' | 'start'>,
): DragSession {
  const px = drawingPx(chart, dates, d)
  return { ...partial, px, originPx: px }
}

/** AI 画线拖拽会话起点（锚点像素快照） */
export function startAiDrag(
  item: AiDrawingItem,
  aiPxNow: Point[],
  partial: Pick<DragSession, 'drawingId' | 'kind' | 'anchorIndex' | 'siblingIds' | 'start'>,
): DragSession {
  const px = aiPxNow.map((pt) => ({ ...pt }))
  return { ...partial, px, originPx: px, ai: { label: item.label } }
}

/**
 * 拖拽帧更新：被抓元素原生位移，兄弟元素镜像 + 像素锚点重算。
 * 返回更新后的会话（px 重算；兄弟镜像为显式副作用）。
 */
export function applyDragMove(
  drag: DragSession,
  target: { x?: number; y?: number } | null | undefined,
  chart: ECharts | null,
): DragSession {
  if (drag.kind === 'move') {
    const dPos = [target?.x ?? 0, target?.y ?? 0]
    if (chart) {
      // 扁平架构：被抓元素由 zrender 原生移动，兄弟元素经 storage 镜像位移
      for (const sid of drag.siblingIds) {
        const el = getZrEl(chart, sid)
        if (el) {
          el.x = dPos[0]
          el.y = dPos[1]
          el.dirty?.()
        }
      }
    }
    return { ...drag, px: drag.originPx.map((pt) => ({ x: pt.x + dPos[0], y: pt.y + dPos[1] })) }
  }
  const hPos = [target?.x ?? 0, target?.y ?? 0]
  return {
    ...drag,
    px: drag.originPx.map((pt, i) => (i === drag.anchorIndex ? { x: pt.x + hPos[0], y: pt.y + hPos[1] } : pt)),
  }
}

/** mouseup 提交：像素锚点回换算为数据锚点（hline 只带价格） */
export function dragAnchors(
  drag: DragSession,
  chart: ECharts,
  dates: string[],
  omitDate: boolean,
): KlineDrawingAnchor[] {
  return drag.px.map((pt) => pxToAnchor(chart, dates, pt, omitDate))
}
