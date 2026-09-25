/**
 * 画线图层 specs 收集层：逐条用户/AI 画线构造 graphic 元素与交互钩子。
 * 重绘调度（sig 短路、setOption、失活 remove、编辑态 chrome）在 layerRender.ts，
 * 指针/键盘事件处理在 layerEvents.ts，元素形状本身在 shapeSpecs.ts。
 */

import type { MutableRefObject } from 'react'
import type { ECharts } from 'echarts'

import { anchorToPx, drawingPx } from './coordinates'
import type { DraftSession } from './draftMachine'
import type { DragSession } from './sessions'
import { startAiDrag, startUserDrag } from './sessions'
import type { DragHooks, GraphicSpec } from './shapeSpecs'
import {
  aiElementIds,
  aiHandleElementIds,
  aiHandleSpecs,
  aiSpecs,
  draftSpecs,
  handleElementIds,
  handleSpecs,
  userElementIds,
  userShapeSpecs,
} from './shapeSpecs'
import { DRAWING_ROOT_PREFIX, type AiDrawingItem, type GridRect, type UseDrawingLayerParams, type UserKlineDrawing } from './types'

/** specs 收集依赖的图层 refs（完整 refs 集见 layerRender.LayerRefs） */
export interface CollectRefs {
  draftRef: MutableRefObject<DraftSession | null>
  /** 当前草稿会话的 graphic id 前缀（startDraft 时生成，会话内唯一） */
  draftIdRef: MutableRefObject<string>
  dragRef: MutableRefObject<DragSession | null>
  liveIdsRef: MutableRefObject<Set<string>>
}

/** 单条用户画线的交互钩子：选中/整体拖拽/锚点拖拽/文字编辑 */
export function userDragHooks(
  d: UserKlineDrawing,
  chart: ECharts,
  p: { current: UseDrawingLayerParams },
  dragRef: MutableRefObject<DragSession | null>,
): DragHooks {
  return {
    onSelect: () => p.current.onSelect(d.id),
    onMoveDragStart: (e) => {
      dragRef.current = startUserDrag(d, chart, p.current.dates, {
        drawingId: d.id,
        kind: 'move',
        anchorIndex: -1,
        siblingIds: userElementIds(d).filter((x) => x !== e.target?.id),
        start: { x: e.offsetX, y: e.offsetY },
      })
    },
    onAnchorDragStart: (i, e) => {
      dragRef.current = startUserDrag(d, chart, p.current.dates, {
        drawingId: d.id,
        kind: 'anchor',
        anchorIndex: i,
        siblingIds: [],
        start: { x: e.offsetX, y: e.offsetY },
      })
    },
    onEditText: () => {
      const a = d.anchors[0]
      if (!a) return
      p.current.onRequestTextInput({
        px: anchorToPx(chart, p.current.dates, a),
        initial: d.text ?? '',
        drawingId: d.id,
      })
    },
  }
}

/** 单条 AI 画线的交互钩子（同用户画线；选中 id 带 ai: 前缀，拖拽会话带 ai.label） */
export function aiDragHooks(
  item: AiDrawingItem,
  aiPxNow: { x: number; y: number }[],
  chart: ECharts,
  p: { current: UseDrawingLayerParams },
  dragRef: MutableRefObject<DragSession | null>,
): DragHooks {
  return {
    onSelect: () => p.current.onSelect(`ai:${item.id}`),
    onMoveDragStart: (e) => {
      dragRef.current = startAiDrag(item, aiPxNow, {
        drawingId: `ai:${item.id}`,
        kind: 'move',
        anchorIndex: -1,
        siblingIds: aiElementIds(item).filter((x) => x !== e.target?.id),
        start: { x: e.offsetX, y: e.offsetY },
      })
    },
    onAnchorDragStart: (i, e) => {
      dragRef.current = startAiDrag(item, aiPxNow, {
        drawingId: `ai:${item.id}`,
        kind: 'anchor',
        anchorIndex: i,
        siblingIds: [],
        start: { x: e.offsetX, y: e.offsetY },
      })
    },
    onEditText: () => {
      const a = item.anchors[0]
      if (!a) return
      p.current.onRequestTextInput({
        px: anchorToPx(chart, p.current.dates, a),
        initial: item.label,
        aiLabel: item.label,
      })
    },
  }
}

/** 逐条画线收集 graphic specs 与存活 id 集（不含失活 remove 与 setOption）；
 * chart 由调用方窄化后传入（非空、未 dispose） */
export function collectGraphicSpecs(
  chart: ECharts,
  p: { current: UseDrawingLayerParams },
  refs: CollectRefs,
  grid: GridRect,
): { specs: GraphicSpec[]; nextIds: Set<string> } {
  const { dates, drawings, aiDrawings, selectedId, activeTool, defaultStyle, interactive } = p.current
  const drag = refs.dragRef.current
  const draft = refs.draftRef.current

  const specs: GraphicSpec[] = []
  const nextIds = new Set<string>()
  const track = (arr: GraphicSpec[]) => {
    for (const s of arr) {
      specs.push(s)
      nextIds.add(String(s.id))
    }
  }

  for (const d of drawings) {
    const dragHere = drag?.drawingId === d.id
    const live = userDragHooks(d, chart, p, refs.dragRef)
    const pxNow = dragHere && drag ? drag.px : drawingPx(chart, dates, d)
    // 锚点拖拽中形状跟随 drag.px 重下发；整体拖拽中形状由 zrender 原生移动 + 兄弟镜像，跳过重下发
    if (!dragHere || drag?.kind === 'anchor') {
      track(userShapeSpecs(d, pxNow, grid, interactive, live))
    } else {
      // 原生移动中的元素保活即可；未渲染过的 id 不虚标（避免对不存在元素发 remove）
      for (const id of userElementIds(d)) {
        if (refs.liveIdsRef.current.has(id)) nextIds.add(id)
      }
    }
    // 整体拖拽中手柄不参与原生移动，按实时 px 重下发跟随；锚点拖拽中手柄是原生移动方，
    // 必须保活——从 storage 移除会让下一帧 hover 落空（target 变主图元素），拖拽即断
    if (interactive && selectedId === d.id) {
      if (!dragHere || drag?.kind === 'move') {
        track(handleSpecs(d, pxNow, live))
      } else {
        for (const id of handleElementIds(d)) {
          if (refs.liveIdsRef.current.has(id)) nextIds.add(id)
        }
      }
    }
  }
  for (const item of aiDrawings) {
    const aiDrag = drag?.ai?.label === item.label ? drag : null
    const aiPxNow = aiDrag && aiDrag.kind === 'anchor' ? aiDrag.px : item.anchors.map((a) => anchorToPx(chart, dates, a))
    const live = aiDragHooks(item, aiPxNow, chart, p, refs.dragRef)
    // 整体拖拽中元素由 zrender 原生移动 + 兄弟镜像，跳过重下发（同用户画线）
    if (!aiDrag || aiDrag.kind === 'anchor') {
      track(aiSpecs(item, aiPxNow, grid, () => {}, interactive && !aiDrag, live))
    } else {
      for (const id of aiElementIds(item)) {
        if (refs.liveIdsRef.current.has(id)) nextIds.add(id)
      }
    }
    if (interactive && selectedId === `ai:${item.id}`) {
      if (!aiDrag || aiDrag.kind === 'move') {
        track(aiHandleSpecs(item, aiPxNow, live))
      } else {
        for (const id of aiHandleElementIds(item)) {
          if (refs.liveIdsRef.current.has(id)) nextIds.add(id)
        }
      }
    }
  }
  if (draft && activeTool) {
    const id = refs.draftIdRef.current || `${DRAWING_ROOT_PREFIX}draft`
    track(draftSpecs(id, draft, grid, defaultStyle.color))
  }

  return { specs, nextIds }
}
