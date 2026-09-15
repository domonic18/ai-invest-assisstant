/**
 * 画线图层 graphic 元素规格构造：用户/AI 两层共用同一 buildShapeSpecs 几何分支，
 * 差异只在样式、命中线 id 与交互属性挂载点。
 *
 * 元素 id 契约（增量 merge / remove 与拖拽兄弟镜像都依赖）：
 * - 用户：`-0` 可见形状、`-1` 命中线（线类常驻，非编辑态无交互属性）、`-h{i}` 选中手柄
 * - AI：`-0` 可见形状、`-1`/`-2` 徽标、`-3` 命中线（仅编辑态）、`-ha{i}` 选中手柄
 */

import { AI_LAYER_COLOR, AI_LAYER_DASH, DRAWING_ROOT_PREFIX } from './types'
import type { AiDrawingItem, GridRect, KlineDrawingType, Point, UserKlineDrawing } from './types'
import { clipRect, clipSegment, extendRay, lineDashArray } from './geometry'
import type { DraftSession } from './draftMachine'

/** graphic 元素 spec 的宽松内部形态（运行时由 ECharts 校验，出口处统一断言） */
export type GraphicSpec = Record<string, unknown>

/** zrender 事件的最小结构面（避免深引 zrender 内部类型） */
export interface ZrEvent {
  offsetX: number
  offsetY: number
  target?: {
    id?: string
    x?: number
    y?: number
    dirty?: () => void
  } | null
}

export interface DragHooks {
  onSelect: () => void
  onMoveDragStart: (e: ZrEvent) => void
  onAnchorDragStart: (anchorIndex: number, e: ZrEvent) => void
  /** 双击文字标注进入编辑（仅 interactive 时挂到元素上） */
  onEditText: () => void
}

/** 画线元素统一层级：displayList 按 (zlevel, z, z2) 排序，主图 series 为 z=2/z2=100，
 * 画线必须压过之，否则点线/手柄被蜡烛体拦截——元素级交互（选中/拖拽/锚点调整）
 * 在锚点落在实体 K 线上时静默失效，画线也被蜡烛遮挡（同花顺式交互优先）。 */
export const ABOVE_SERIES_LAYERING = { z: 2, z2: 500 }

function lineSpec(
  id: string,
  p1: Point,
  p2: Point,
  style: { color: string; dash: number[]; width: number; opacity?: number },
  extra?: Record<string, unknown>,
): GraphicSpec {
  return {
    id,
    position: [0, 0],
    ...ABOVE_SERIES_LAYERING,
    type: 'line',
    shape: { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y },
    style: {
      stroke: style.color,
      lineWidth: style.width,
      opacity: style.opacity ?? 1,
      lineDash: style.dash.length ? style.dash : undefined,
    },
    ...extra,
  }
}

/** 透明加粗命中线（覆盖可见线上方，承接 click/drag） */
function hitLineSpec(id: string, p1: Point, p2: Point, extra: Record<string, unknown>): GraphicSpec {
  return {
    id,
    position: [0, 0],
    ...ABOVE_SERIES_LAYERING,
    type: 'line',
    shape: { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y },
    style: { stroke: '#000', lineWidth: 10, opacity: 0 },
    ...extra,
  }
}

export interface ShapeSpecsParams {
  /** 元素 id 前缀（不含 -0/-1 等后缀） */
  baseId: string
  drawingType: KlineDrawingType
  anchorsPx: Point[]
  grid: GridRect
  style: { color: string; dash: number[]; width: number; opacity?: number }
  /** drawingType=text 的显示内容 */
  text?: string
  /** drawingType=ray 的延伸方向 */
  direction?: 'left' | 'right' | 'both'
  /** 叠加于可见形状的基础属性（AI 层 hover 事件；用户层不传） */
  extras?: Record<string, unknown>
  /** 交互属性：线类挂命中线、box/text 挂形状自身（非编辑态传空） */
  moveProps?: Record<string, unknown>
  /** 命中线元素完整 id；不传则不生成命中线（AI 非编辑态） */
  hitId?: string
}

/** 单条画线 → 顶层元素 specs：用户/AI 两层统一的按类型几何分支 */
export function buildShapeSpecs(p: ShapeSpecsParams): GraphicSpec[] {
  const { baseId, drawingType, anchorsPx: px, grid } = p
  const extras = p.extras ?? {}
  const moveProps = p.moveProps ?? {}
  const specs: GraphicSpec[] = []
  if (drawingType === 'hline') {
    const y = px[0].y
    const vis = clipSegment({ x: grid.x, y }, { x: grid.x + grid.width, y }, grid)
    if (vis) {
      specs.push(lineSpec(`${baseId}-0`, vis[0], vis[1], p.style, extras))
      if (p.hitId) specs.push(hitLineSpec(p.hitId, vis[0], vis[1], moveProps))
    }
  } else if (drawingType === 'box') {
    const rect = clipRect(px[0], px[1], grid)
    if (rect) {
      specs.push({
        id: `${baseId}-0`,
        position: [0, 0],
        ...ABOVE_SERIES_LAYERING,
        type: 'rect',
        shape: rect,
        style: {
          fill: p.style.color,
          fillOpacity: 0.08,
          stroke: p.style.color,
          lineWidth: p.style.width,
          lineDash: p.style.dash.length ? p.style.dash : undefined,
          opacity: p.style.opacity ?? 1,
        },
        ...extras,
        ...moveProps,
      })
    }
  } else if (drawingType === 'text') {
    specs.push({
      id: `${baseId}-0`,
      position: [0, 0],
      ...ABOVE_SERIES_LAYERING,
      type: 'text',
      x: px[0].x,
      y: px[0].y,
      style: { text: p.text ?? '', fill: p.style.color, fontSize: 12, fontWeight: 600 },
      ...extras,
      ...moveProps,
    })
  } else {
    const [s, e] =
      drawingType === 'ray' ? extendRay(px[0], px[1], grid, p.direction ?? 'right') : [px[0], px[1]]
    const vis = clipSegment(s, e, grid)
    if (vis) {
      specs.push(lineSpec(`${baseId}-0`, vis[0], vis[1], p.style, extras))
      if (p.hitId) specs.push(hitLineSpec(p.hitId, vis[0], vis[1], moveProps))
    }
  }
  return specs
}

/** 单条用户画线 → 顶层元素 specs（可见形状 + 命中线 -1 常驻；编辑态挂选中/拖拽） */
export function userShapeSpecs(
  d: UserKlineDrawing,
  px: Point[],
  grid: GridRect,
  interactive: boolean,
  hooks: DragHooks,
): GraphicSpec[] {
  const base = `${DRAWING_ROOT_PREFIX}user-${d.id}`
  // 非编辑态不挂任何交互属性（同花顺式：退出画线后图形纯展示，不可选中/拖动）
  const moveProps: Record<string, unknown> = interactive
    ? {
        cursor: 'move',
        draggable: true,
        onclick: hooks.onSelect,
        onmousedown: hooks.onMoveDragStart,
      }
    : {}
  return buildShapeSpecs({
    baseId: base,
    drawingType: d.drawingType,
    anchorsPx: px,
    grid,
    style: {
      color: d.style.color,
      dash: lineDashArray(d.style.lineStyle),
      width: d.style.width,
    },
    text: d.text || '未命名标注',
    direction: d.direction ?? 'right',
    moveProps: interactive && d.drawingType === 'text' ? { ...moveProps, ondblclick: () => hooks.onEditText() } : moveProps,
    hitId: `${base}-1`,
  })
}

/** 单条用户画线的全部顶层元素 id：`-0` 可见形状、`-1` 命中线（仅线类有） */
export function userElementIds(d: Pick<UserKlineDrawing, 'id' | 'drawingType'>): string[] {
  const base = `${DRAWING_ROOT_PREFIX}user-${d.id}`
  const lineLike = d.drawingType === 'hline' || d.drawingType === 'trendline' || d.drawingType === 'ray'
  return lineLike ? [`${base}-0`, `${base}-1`] : [`${base}-0`]
}

/** 选中手柄元素 id（锚点数量一一对应） */
export function handleElementIds(d: Pick<UserKlineDrawing, 'id' | 'anchors'>): string[] {
  const base = `${DRAWING_ROOT_PREFIX}user-${d.id}`
  return d.anchors.map((_, i) => `${base}-h${i}`)
}

/** 选中手柄（顶层元素；锚点拖拽时形状元素可安全重下发） */
export function handleSpecs(d: UserKlineDrawing, px: Point[], hooks: DragHooks): GraphicSpec[] {
  const base = `${DRAWING_ROOT_PREFIX}user-${d.id}`
  return px.map((p, i) => ({
    id: `${base}-h${i}`,
    position: [0, 0],
    ...ABOVE_SERIES_LAYERING,
    type: 'circle',
    shape: { cx: p.x, cy: p.y, r: 4.5 },
    style: { fill: '#16181f', stroke: d.style.color, lineWidth: 1.5 },
    cursor: 'crosshair',
    draggable: true,
    onmousedown: (e: ZrEvent) => hooks.onAnchorDragStart(i, e),
  }))
}

/** AI 画线 → 顶层元素 specs（虚线锁定样式 + AI 徽标；编辑态挂选中/拖拽/双击改名） */
export function aiSpecs(
  item: AiDrawingItem,
  px: Point[],
  grid: GridRect,
  onHover: (item: AiDrawingItem | null) => void,
  interactive = false,
  hooks?: DragHooks,
): GraphicSpec[] {
  const base = `${DRAWING_ROOT_PREFIX}ai-${item.id}`
  const hover = { onmouseover: () => onHover(item), onmouseout: () => onHover(null) }
  // 编辑态交互属性（双击改 label）；非编辑态退化为 hover 展示
  const edit = interactive && hooks
  const moveProps: Record<string, unknown> = edit
    ? {
        cursor: 'move',
        draggable: true,
        onclick: hooks!.onSelect,
        onmousedown: hooks!.onMoveDragStart,
        ondblclick: hooks!.onEditText,
      }
    : {}
  const specs = buildShapeSpecs({
    baseId: base,
    drawingType: item.drawingType,
    anchorsPx: px,
    grid,
    style: { color: AI_LAYER_COLOR, dash: AI_LAYER_DASH, width: 1.6, opacity: 0.92 },
    text: item.label,
    direction: item.direction ?? 'right',
    extras: hover,
    moveProps,
    hitId: edit ? `${base}-3` : undefined,
  })
  // AI 徽标（首个锚点偏移，与原型一致）：绝对坐标平铺为 rect + text 两元素
  specs.push(
    {
      id: `${base}-1`,
      position: [0, 0],
      ...ABOVE_SERIES_LAYERING,
      type: 'rect',
      shape: { x: px[0].x + 8, y: px[0].y - 20, width: 20, height: 12, r: 3 },
      style: { fill: 'rgba(94,106,210,.22)', stroke: '#5e6ad2', lineWidth: 0.8 },
      ...hover,
    },
    {
      id: `${base}-2`,
      position: [0, 0],
      ...ABOVE_SERIES_LAYERING,
      type: 'text',
      x: px[0].x + 18,
      y: px[0].y - 11,
      style: {
        text: 'AI',
        fill: '#8a93ff',
        fontSize: 8,
        fontWeight: 700,
        align: 'center',
        verticalAlign: 'middle',
      },
      ...hover,
    },
  )
  return specs
}

/** AI 画线全部顶层元素 id（-0 可见形状 / -1 -2 徽标 / -3 命中线（lineLike）） */
export function aiElementIds(item: AiDrawingItem): string[] {
  const base = `${DRAWING_ROOT_PREFIX}ai-${item.id}`
  const lineLike =
    item.drawingType === 'hline' || item.drawingType === 'trendline' || item.drawingType === 'ray'
  return lineLike ? [`${base}-0`, `${base}-1`, `${base}-2`, `${base}-3`] : [`${base}-0`, `${base}-1`, `${base}-2`]
}

/** AI 画线选中手柄元素 id */
export function aiHandleElementIds(item: AiDrawingItem): string[] {
  const base = `${DRAWING_ROOT_PREFIX}ai-${item.id}`
  return item.anchors.map((_, i) => `${base}-ha${i}`)
}

/** AI 画线选中手柄（锚点拖拽；描边取 AI 视觉色） */
export function aiHandleSpecs(item: AiDrawingItem, px: Point[], hooks: DragHooks): GraphicSpec[] {
  const base = `${DRAWING_ROOT_PREFIX}ai-${item.id}`
  return px.map((p, i) => ({
    id: `${base}-ha${i}`,
    position: [0, 0],
    ...ABOVE_SERIES_LAYERING,
    type: 'circle',
    shape: { cx: p.x, cy: p.y, r: 4.5 },
    style: { fill: '#16181f', stroke: AI_LAYER_COLOR, lineWidth: 1.5 },
    cursor: 'crosshair',
    draggable: true,
    onmousedown: (e: ZrEvent) => hooks.onAnchorDragStart(i, e),
  }))
}

/** 草稿预览（首锚点 + 跟随光标；箱体画矩形预览，其余画虚线段） */
export function draftSpecs(id: string, draft: DraftSession, grid: GridRect, color: string): GraphicSpec[] {
  const specs: GraphicSpec[] = [
    {
      id: `${id}-0`,
      position: [0, 0],
      ...ABOVE_SERIES_LAYERING,
      type: 'circle',
      shape: { cx: draft.startPx.x, cy: draft.startPx.y, r: 4 },
      style: { fill: color, stroke: '#16181f', lineWidth: 1 },
    },
  ]
  if (draft.tool === 'box') {
    const rect = clipRect(draft.startPx, draft.cursorPx, grid)
    if (rect) {
      specs.push({
        id: `${id}-1`,
        position: [0, 0],
        ...ABOVE_SERIES_LAYERING,
        type: 'rect',
        shape: rect,
        style: { fill: color, fillOpacity: 0.08, stroke: color, lineWidth: 1.5, lineDash: [4, 4] },
      })
    }
  } else {
    const vis = clipSegment(draft.startPx, draft.cursorPx, grid)
    if (vis) specs.push(lineSpec(`${id}-1`, vis[0], vis[1], { color, dash: [4, 4], width: 1.5 }))
  }
  return specs
}
