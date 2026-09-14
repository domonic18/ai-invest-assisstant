/**
 * 画线图层生命周期 hook：接 ECharts 实例，承担画线渲染/重定位/命中/拖拽。
 *
 * 设计要点（docs/arch/09-kline-drawing.md §3.2）：
 * - 锚点存数据坐标 (date, price)，像素只在渲染瞬间经 convertToPixel/convertFromPixel 存在；
 * - 按 graphic 元素 id 增量 merge + 失活 remove，禁止整图 setOption（保拖拽帧率）；
 * - 扁平元素架构：可见形状/命中线/手柄/徽标都是带唯一 id 的顶层元素，不用 group children。
 *   echarts 父组簿记在「旧 id remove + 新 id replace」组合下会把 id-less 子元素与孤儿条目按
 *   index 错配（createEl 拿到 undefined 父容器直接抛错），且 replace 移除 group 存在 traverse
 *   边删边遍历缺陷；扁平 merge + 逐元素 remove 完全绕开这两处；
 * - 整体拖拽由 zrender 原生移动被抓元素，兄弟元素经 zr.storage 镜像 position；
 * - 画线由 draftMachine 状态机驱动：双锚点工具 mousedown/mouseup 双模（点击两下/按住拖拽），
 *   单锚点工具 click 直接提交；成线后工具保持激活可连续画线，Esc 退出；空点取消选中
 *   只忽略画线图层自有元素，主图元素不拦截；
 * - armed 状态与全部 dataZoom 互斥，并隐藏主图 tooltip/十字指示器（编辑态）；图层异常静默降级为不渲染。
 */

import type { ECharts, EChartsOption } from 'echarts'
import { useEffect, useRef } from 'react'

import {
  type DraftSession,
  isTwoAnchorTool,
  moveDraft,
  pressSecond,
  releaseDraft,
  startDraft,
} from './draftMachine'
import {
  anchorToIndex,
  clipRect,
  clipSegment,
  extendRay,
  GridRect,
  lineDashArray,
  Point,
  roundPrice,
} from './geometry'
import {
  AI_LAYER_COLOR,
  AI_LAYER_DASH,
  AiKlineDrawingItem,
  DRAWING_ROOT_PREFIX,
  KlineDrawingAnchor,
  KlineDrawingStyle,
  KlineDrawingType,
  UserKlineDrawing,
  UserKlineDrawingCreateRequest,
  UserKlineDrawingUpdateRequest,
} from './types'

/** graphic 元素 spec 的宽松内部形态（运行时由 ECharts 校验，出口处统一断言） */
type GraphicSpec = Record<string, unknown>

/** AI 画线稳定 id（集成层按 `${groupKey}:${label}` 生成） */
export type AiDrawingItem = AiKlineDrawingItem & { id: string }

/** 无位移拖拽（纯点击）不提交更新 */
function dragMoved(drag: DragSession): boolean {
  return drag.px.some((pt, i) => pt.x !== drag.originPx[i].x || pt.y !== drag.originPx[i].y)
}

/** 文字标注输入请求（新建：anchor 预计算；编辑：drawingId + initial） */
export interface DrawingTextEditRequest {
  /** 图表容器内像素位置（输入框定位） */
  px: Point
  /** 新建时点击处的数据锚点 */
  anchor?: KlineDrawingAnchor
  /** 编辑已有文字标注 */
  drawingId?: string
  initial?: string
}

/** 草稿 group id 会话内唯一：固定 id 的孤儿子条目会被下一草稿按 id 复配到已移除的父组上 */
let draftSeq = 0

export interface DrawingScope {
  targetType: 'stock' | 'index' | 'sector'
  targetCode: string
  period: 'daily' | 'weekly' | 'monthly'
}

export interface UseDrawingLayerParams {
  /** echarts-for-react 实例；null 时图层整体静默 */
  chart: ECharts | null
  /** 主图 category x 轴日期序列（与图表 option 同源） */
  dates: string[]
  /** 画线归属域（构造创建请求用） */
  scope: DrawingScope
  /** 当前周期已过滤的用户画线 */
  drawings: UserKlineDrawing[]
  /** 当前周期已过滤的 AI 画线（一期只读渲染，二期原位编辑） */
  aiDrawings: AiDrawingItem[]
  /** 画线工具（null = 未进入画线模式） */
  activeTool: KlineDrawingType | null
  selectedId: string | null
  /** 编辑态（左缘工具栏可见）：仅编辑态下画线可选中/拖动，退出后纯展示（同花顺式） */
  interactive: boolean
  /** 新画线默认样式（记忆值） */
  defaultStyle: KlineDrawingStyle
  onCreate: (req: UserKlineDrawingCreateRequest) => void
  onUpdate: (id: string, patch: UserKlineDrawingUpdateRequest) => void
  onSelect: (id: string | null) => void
  onDelete: (id: string) => void
  /** Esc 退出画线模式（集成层清空 activeTool） */
  onRequestDisarm: () => void
  /** Esc 最后一级：退出画线编辑态（收起竖排工具栏） */
  onRequestExit?: () => void
  /** 文字工具点击落点 / 双击已有文字标注：请求宿主弹出文字输入框 */
  onRequestTextInput: (req: DrawingTextEditRequest) => void
}

/** zrender 事件的最小结构面（避免深引 zrender 内部类型） */
interface ZrEvent {
  offsetX: number
  offsetY: number
  target?: {
    id?: string
    x?: number
    y?: number
    dirty?: () => void
  } | null
}

interface DragSession {
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
}

/** 命中元素是否属于画线图层（沿 parent 链找命名空间 id；K 线/均线等主图元素不算） */
function isDrawingElement(target: unknown): boolean {
  let el = target as { id?: unknown; parent?: unknown } | null
  while (el) {
    if (typeof el.id === 'string' && el.id.startsWith(DRAWING_ROOT_PREFIX)) return true
    el = el.parent as typeof el
  }
  return false
}

/** 主图 grid 矩形（内部 API，取不到返回 null 降级） */
function getMainGridRect(chart: ECharts): GridRect | null {
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

function inRect(x: number, y: number, r: GridRect): boolean {
  return x >= r.x && x <= r.x + r.width && y >= r.y && y <= r.y + r.height
}

/** 当前 option 的 dataZoom 条目数（armed 时需全部禁用，图表可能同时配 inside+slider） */
function dataZoomCount(chart: ECharts): number {
  try {
    const opt = chart.getOption() as { dataZoom?: unknown } | undefined
    return Array.isArray(opt?.dataZoom) ? opt.dataZoom.length : 0
  } catch {
    return 0
  }
}

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
    type: 'line',
    shape: { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y },
    style: { stroke: '#000', lineWidth: 10, opacity: 0 },
    ...extra,
  }
}

/** 单条画线的全部顶层元素 id：`-0` 可见形状、`-1` 命中线（仅线类有） */
function userElementIds(d: Pick<UserKlineDrawing, 'id' | 'drawingType'>): string[] {
  const base = `${DRAWING_ROOT_PREFIX}user-${d.id}`
  const lineLike = d.drawingType === 'hline' || d.drawingType === 'trendline' || d.drawingType === 'ray'
  return lineLike ? [`${base}-0`, `${base}-1`] : [`${base}-0`]
}

/** zrender storage 内部 API：按 id 取存活元素（拖拽兄弟镜像与图层擦除探测用） */
function getZrEl(chart: ECharts, id: string): { x?: number; y?: number; dirty?: () => void } | undefined {
  const storage = (
    chart.getZr() as unknown as {
      storage?: { getDisplayList?: () => ({ id?: unknown; x?: number; y?: number; dirty?: () => void } | undefined)[] }
    }
  ).storage
  return storage?.getDisplayList?.().find((el) => el && el.id === id)
}

interface DragHooks {
  onSelect: () => void
  onMoveDragStart: (e: ZrEvent) => void
  onAnchorDragStart: (anchorIndex: number, e: ZrEvent) => void
  /** 双击文字标注进入编辑（仅 interactive 时挂到元素上） */
  onEditText: () => void
}

/** 单条用户画线 → 顶层元素 specs（可见形状 + 命中线；merge 更新，删除走逐元素 remove） */
function userShapeSpecs(
  d: UserKlineDrawing,
  px: Point[],
  grid: GridRect,
  interactive: boolean,
  hooks: DragHooks,
): GraphicSpec[] {
  const style = {
    color: d.style.color,
    dash: lineDashArray(d.style.lineStyle),
    width: d.style.width,
  }
  // 非编辑态不挂任何交互属性（同花顺式：退出画线后图形纯展示，不可选中/拖动）
  const moveProps: Record<string, unknown> = interactive
    ? {
        cursor: 'move',
        draggable: true,
        onclick: hooks.onSelect,
        onmousedown: hooks.onMoveDragStart,
      }
    : {}
  const base = `${DRAWING_ROOT_PREFIX}user-${d.id}`
  const specs: GraphicSpec[] = []

  if (d.drawingType === 'hline') {
    const y = px[0].y
    const vis = clipSegment({ x: grid.x, y }, { x: grid.x + grid.width, y }, grid)
    if (vis) {
      specs.push(lineSpec(`${base}-0`, vis[0], vis[1], style), hitLineSpec(`${base}-1`, vis[0], vis[1], moveProps))
    }
  } else if (d.drawingType === 'box') {
    const rect = clipRect(px[0], px[1], grid)
    if (rect) {
      specs.push({
        id: `${base}-0`,
        position: [0, 0],
        type: 'rect',
        shape: rect,
        style: {
          fill: d.style.color,
          fillOpacity: 0.08,
          stroke: d.style.color,
          lineWidth: d.style.width,
        },
        ...moveProps,
      })
    }
  } else if (d.drawingType === 'text') {
    specs.push({
      id: `${base}-0`,
      position: [0, 0],
      type: 'text',
      x: px[0].x,
      y: px[0].y,
      style: {
        text: d.text || '未命名标注',
        fill: d.style.color,
        fontSize: 12,
        fontWeight: 600,
      },
      ...moveProps,
      ...(interactive ? { ondblclick: () => hooks.onEditText() } : {}),
    })
  } else {
    const [s, e] =
      d.drawingType === 'ray' ? extendRay(px[0], px[1], grid, d.direction ?? 'right') : [px[0], px[1]]
    const vis = clipSegment(s, e, grid)
    if (vis) {
      specs.push(lineSpec(`${base}-0`, vis[0], vis[1], style), hitLineSpec(`${base}-1`, vis[0], vis[1], moveProps))
    }
  }
  return specs
}

/** 选中手柄（顶层元素；锚点拖拽时形状元素可安全重下发） */
function handleSpecs(d: UserKlineDrawing, px: Point[], hooks: DragHooks): GraphicSpec[] {
  const base = `${DRAWING_ROOT_PREFIX}user-${d.id}`
  return px.map((p, i) => ({
    id: `${base}-h${i}`,
    position: [0, 0],
    type: 'circle',
    shape: { cx: p.x, cy: p.y, r: 4.5 },
    style: { fill: '#16181f', stroke: d.style.color, lineWidth: 1.5 },
    cursor: 'crosshair',
    draggable: true,
    onmousedown: (e: ZrEvent) => hooks.onAnchorDragStart(i, e),
  }))
}

/** AI 画线 → 只读顶层元素 specs（虚线锁定样式 + AI 徽标 + hover 回调） */
function aiSpecs(
  item: AiDrawingItem,
  px: Point[],
  grid: GridRect,
  onHover: (item: AiDrawingItem | null) => void,
): GraphicSpec[] {
  const style = { color: AI_LAYER_COLOR, dash: AI_LAYER_DASH, width: 1.6, opacity: 0.92 }
  const hover = { onmouseover: () => onHover(item), onmouseout: () => onHover(null) }
  const base = `${DRAWING_ROOT_PREFIX}ai-${item.id}`
  const specs: GraphicSpec[] = []
  if (item.drawingType === 'hline') {
    const y = px[0].y
    const vis = clipSegment({ x: grid.x, y }, { x: grid.x + grid.width, y }, grid)
    if (vis) specs.push(lineSpec(`${base}-0`, vis[0], vis[1], style, hover))
  } else if (item.drawingType === 'box') {
    const rect = clipRect(px[0], px[1], grid)
    if (rect) {
      specs.push({
        id: `${base}-0`,
        position: [0, 0],
        type: 'rect',
        shape: rect,
        style: {
          fill: AI_LAYER_COLOR,
          fillOpacity: 0.08,
          stroke: AI_LAYER_COLOR,
          lineWidth: 1.6,
          lineDash: AI_LAYER_DASH,
          opacity: 0.92,
        },
        ...hover,
      })
    }
  } else if (item.drawingType === 'text') {
    specs.push({
      id: `${base}-0`,
      position: [0, 0],
      type: 'text',
      x: px[0].x,
      y: px[0].y,
      style: { text: item.label, fill: AI_LAYER_COLOR, fontSize: 12, fontWeight: 600 },
      ...hover,
    })
  } else {
    const [s, e] =
      item.drawingType === 'ray' ? extendRay(px[0], px[1], grid, item.direction ?? 'right') : [px[0], px[1]]
    const vis = clipSegment(s, e, grid)
    if (vis) specs.push(lineSpec(`${base}-0`, vis[0], vis[1], style, hover))
  }
  // AI 徽标（首个锚点偏移，与原型一致）：绝对坐标平铺为 rect + text 两元素
  specs.push(
    {
      id: `${base}-1`,
      position: [0, 0],
      type: 'rect',
      shape: { x: px[0].x + 8, y: px[0].y - 20, width: 20, height: 12, r: 3 },
      style: { fill: 'rgba(94,106,210,.22)', stroke: '#5e6ad2', lineWidth: 0.8 },
      ...hover,
    },
    {
      id: `${base}-2`,
      position: [0, 0],
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

/** 草稿预览（首锚点 + 跟随光标；箱体画矩形预览，其余画虚线段） */
function draftSpecs(id: string, draft: DraftSession, grid: GridRect, color: string): GraphicSpec[] {
  const specs: GraphicSpec[] = [
    {
      id: `${id}-0`,
      position: [0, 0],
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

export function useDrawingLayer(params: UseDrawingLayerParams): {
  /** 选中画线首锚点的像素位置（StyleBar 定位用） */
  getSelectedPixelPos: () => Point | null
} {
  const p = useRef(params)
  p.current = params
  const draftRef = useRef<DraftSession | null>(null)
  /** 当前草稿会话的 graphic id 前缀（startDraft 时生成，会话内唯一） */
  const draftIdRef = useRef('')
  const dragRef = useRef<DragSession | null>(null)
  /** 成线提交后的 click 抑制（mousedown/mouseup 成线仍会派发一次 click，避免误清选中） */
  const suppressClickRef = useRef(false)
  const sigRef = useRef('')
  const liveIdsRef = useRef<Set<string>>(new Set())
  const zoomDisabledRef = useRef(false)
  /** armed 时被隐藏的主图浮层原状态（tooltip/axisPointer），退出时按原值还原 */
  const savedChromeRef = useRef<{ tooltip: boolean; axisPointer: boolean } | null>(null)

  const anchorToPx = (chart: ECharts, dates: string[], a: KlineDrawingAnchor): Point => ({
    x: chart.convertToPixel({ xAxisIndex: 0 }, anchorToIndex(a, dates)),
    y: chart.convertToPixel({ yAxisIndex: 0 }, a.price),
  })

  /** 像素 → 数据锚点；hline 只承载价格（后端契约：水平线锚点不带 date） */
  const pxToAnchor = (
    chart: ECharts,
    dates: string[],
    pt: Point,
    omitDate = false,
  ): KlineDrawingAnchor => {
    const price = roundPrice(chart.convertFromPixel({ yAxisIndex: 0 }, pt.y))
    if (omitDate || !dates.length) return { date: '', price }
    const idx = Math.round(chart.convertFromPixel({ xAxisIndex: 0 }, pt.x))
    const clamped = Math.min(Math.max(idx, 0), dates.length - 1)
    return { date: dates[clamped] ?? '', price }
  }

  const drawingPx = (chart: ECharts, dates: string[], d: UserKlineDrawing): Point[] =>
    d.anchors.map((a) => anchorToPx(chart, dates, a))

  const commitDraft = (pxs: Point[]) => {
    const { chart, dates, scope, activeTool, defaultStyle, onCreate } = p.current
    if (!chart || !activeTool) return
    const anchors = pxs.map((pt) => pxToAnchor(chart, dates, pt, activeTool === 'hline'))
    onCreate({
      targetType: scope.targetType,
      targetCode: scope.targetCode,
      period: scope.period,
      drawingType: activeTool,
      anchors,
      direction: activeTool === 'ray' ? 'right' : undefined,
      style: defaultStyle,
    })
  }

  const finishDrag = () => {
    const drag = dragRef.current
    dragRef.current = null
    if (!drag || !dragMoved(drag)) return
    const { chart, dates, drawings, onUpdate } = p.current
    if (!chart) return
    const omitDate = drawings.find((d) => d.id === drag.drawingId)?.drawingType === 'hline'
    onUpdate(drag.drawingId, {
      anchors: drag.px.map((pt) => pxToAnchor(chart, dates, pt, omitDate)),
    })
  }

  /** 增量渲染：merge-by-id + 失活 remove；被拖拽元素跳过重下发（zrender 原生移动中） */
  const render = () => {
    const { chart, dates, drawings, aiDrawings, selectedId, activeTool, defaultStyle, interactive } = p.current
    if (!chart || chart.isDisposed() || dates.length === 0) return
    const grid = getMainGridRect(chart)
    if (!grid) return

    const drag = dragRef.current
    const draft = draftRef.current
    const sig = JSON.stringify([drawings, aiDrawings, selectedId, activeTool, interactive, dates.length, grid, draft, drag?.px])
    if (sig === sigRef.current) return

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
      const live: DragHooks = {
        onSelect: () => p.current.onSelect(d.id),
        onMoveDragStart: (e) => {
          dragRef.current = {
            drawingId: d.id,
            kind: 'move',
            anchorIndex: -1,
            siblingIds: userElementIds(d).filter((x) => x !== e.target?.id),
            px: drawingPx(chart, p.current.dates, d),
            originPx: drawingPx(chart, p.current.dates, d),
            start: { x: e.offsetX, y: e.offsetY },
          }
        },
        onAnchorDragStart: (i, e) => {
          dragRef.current = {
            drawingId: d.id,
            kind: 'anchor',
            anchorIndex: i,
            siblingIds: [],
            px: drawingPx(chart, p.current.dates, d),
            originPx: drawingPx(chart, p.current.dates, d),
            start: { x: e.offsetX, y: e.offsetY },
          }
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
      const pxNow = dragHere && drag ? drag.px : drawingPx(chart, dates, d)
      // 锚点拖拽中形状跟随 drag.px 重下发；整体拖拽中形状由 zrender 原生移动 + 兄弟镜像，跳过重下发
      if (!dragHere || drag?.kind === 'anchor') {
        track(userShapeSpecs(d, pxNow, grid, interactive, live))
      } else {
        // 原生移动中的元素保活即可；未渲染过的 id 不虚标（避免对不存在元素发 remove）
        for (const id of userElementIds(d)) {
          if (liveIdsRef.current.has(id)) nextIds.add(id)
        }
      }
      // 整体拖拽中手柄不参与原生移动，按实时 px 重下发跟随
      if (interactive && selectedId === d.id && (!dragHere || drag?.kind === 'move')) {
        track(handleSpecs(d, pxNow, live))
      }
    }
    for (const item of aiDrawings) {
      track(
        aiSpecs(
          item,
          item.anchors.map((a) => anchorToPx(chart, dates, a)),
          grid,
          () => {},
        ),
      )
    }
    if (draft && activeTool) {
      const id = draftIdRef.current || `${DRAWING_ROOT_PREFIX}draft`
      track(draftSpecs(id, draft, grid, defaultStyle.color))
    }

    const removed: GraphicSpec[] = []
    for (const id of liveIdsRef.current) {
      if (!nextIds.has(id)) removed.push({ id, $action: 'remove' })
    }
    if (specs.length || removed.length) {
      try {
        chart.setOption({ graphic: [...specs, ...removed] } as unknown as EChartsOption)
      } catch (err) {
        // sig/liveIds 只在 setOption 成功后落地，失败时下一帧重试（否则整层冻结到刷新）
        console.warn('[drawing] 图层降级', err)
        sigRef.current = ''
        return
      }
    }
    sigRef.current = sig
    liveIdsRef.current = nextIds

    // armed 与全部 dataZoom 互斥（滚轮/拖动不缩放）；同时隐藏 K 线 tooltip/十字指示器，
    // 避免悬浮数据点压住画线预览（同花顺式编辑态）
    const wantDisable = !!activeTool
    if (wantDisable !== zoomDisabledRef.current) {
      const count = dataZoomCount(chart)
      if (count > 0) {
        chart.setOption({
          dataZoom: Array.from({ length: count }, () => ({ disabled: wantDisable })),
        } as EChartsOption)
      }
      zoomDisabledRef.current = wantDisable
      try {
        if (wantDisable) {
          const opt = chart.getOption() as {
            tooltip?: { show?: boolean }
            axisPointer?: { show?: boolean }
          }
          savedChromeRef.current = {
            tooltip: opt.tooltip?.show !== false,
            axisPointer: opt.axisPointer?.show !== false,
          }
          chart.setOption({ tooltip: { show: false }, axisPointer: { show: false } } as EChartsOption)
        } else if (savedChromeRef.current) {
          const saved = savedChromeRef.current
          savedChromeRef.current = null
          chart.setOption({
            tooltip: { show: saved.tooltip },
            axisPointer: { show: saved.axisPointer },
          } as EChartsOption)
        }
      } catch {
        /* 图表 option 异常不阻断画线 */
      }
    }
  }

  /** zrender 拖拽实时移动：被抓元素原生位移，兄弟元素镜像 + 像素锚点重算 */
  const handleDragMove = (e: ZrEvent) => {
    const drag = dragRef.current
    if (!drag) return
    const target = e.target
    if (drag.kind === 'move') {
      const dPos = [target?.x ?? 0, target?.y ?? 0]
      const chart = p.current.chart
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
      drag.px = drag.originPx.map((pt) => ({ x: pt.x + dPos[0], y: pt.y + dPos[1] }))
    } else {
      const hPos = [target?.x ?? 0, target?.y ?? 0]
      drag.px = drag.originPx.map((pt, i) =>
        i === drag.anchorIndex ? { x: pt.x + hPos[0], y: pt.y + hPos[1] } : pt,
      )
    }
    try {
      render()
    } catch (err) {
      console.warn('[drawing] 图层降级', err)
    }
  }

  useEffect(() => {
    const chart = params.chart
    if (!chart) return
    const schedule = () => {
      try {
        // 主图 notMerge 重建会整层擦除 graphic：探测首个存活元素，被擦除则强制重渲染
        const sample = liveIdsRef.current.values().next().value as string | undefined
        if (sample && !getZrEl(chart, sample)) sigRef.current = ''
        render()
      } catch (err) {
        console.warn('[drawing] 图层降级', err)
      }
    }
    /** 画线模式首次按下：双锚点工具开草稿（等待拖拽或松开转点击式） */
    const onZrMouseDown = (ev: unknown) => {
      const e = ev as ZrEvent
      const { chart: c, dates, activeTool } = p.current
      if (!c || dates.length === 0 || !activeTool) return
      const grid = getMainGridRect(c)
      if (!grid || !inRect(e.offsetX, e.offsetY, grid)) return
      const pt = { x: e.offsetX, y: e.offsetY }
      const draft = draftRef.current
      if (draft && draft.phase === 'awaitSecond') {
        // 第二锚点：即使落在已有画线/主图元素上也成线；工具保持激活可连续画线
        const t = pressSecond(draft, pt)
        draftRef.current = t.session
        suppressClickRef.current = true
        if (t.commit) commitDraft(t.commit)
        sigRef.current = ''
        render()
        return
      }
      if (!draft && isTwoAnchorTool(activeTool)) {
        dragRef.current = null // 画线模式抢占元素级拖拽
        draftRef.current = startDraft(activeTool, pt)
        draftIdRef.current = `${DRAWING_ROOT_PREFIX}draft-${++draftSeq}`
        sigRef.current = ''
        render()
      }
    }
    const onZrClick = (ev: unknown) => {
      if (suppressClickRef.current) {
        suppressClickRef.current = false
        return
      }
      const e = ev as ZrEvent
      const { chart: c, dates, activeTool } = p.current
      if (!c || dates.length === 0) return
      const grid = getMainGridRect(c)
      if (!grid || !inRect(e.offsetX, e.offsetY, grid)) return
      if (activeTool) {
        // 双锚点工具成线由 mousedown/mouseup 状态机驱动；文字工具点击弹出输入框；
        // 其余单锚点工具单击即成线（忽略主图元素）
        if (activeTool === 'text') {
          const pt = { x: e.offsetX, y: e.offsetY }
          p.current.onRequestTextInput({ px: pt, anchor: pxToAnchor(c, dates, pt) })
        } else if (!isTwoAnchorTool(activeTool)) {
          commitDraft([{ x: e.offsetX, y: e.offsetY }])
        }
        return
      }
      if (e.target && isDrawingElement(e.target)) return // 元素级 onclick 已处理选中
      p.current.onSelect(null)
    }
    const onZrMousemove = (ev: unknown) => {
      const e = ev as ZrEvent
      const { chart: c, activeTool } = p.current
      // 编辑态强制十字光标（含悬在主图元素上时）
      if (c && activeTool && (!e.target || draftRef.current)) c.getZr().setCursorStyle('crosshair')
      if (dragRef.current) {
        handleDragMove(e)
        return
      }
      if (draftRef.current) {
        const t = moveDraft(draftRef.current, { x: e.offsetX, y: e.offsetY })
        draftRef.current = t.session
        sigRef.current = ''
        render()
      }
    }
    const onZrMouseup = (ev: unknown) => {
      if (dragRef.current) {
        finishDrag()
        return
      }
      const e = ev as ZrEvent
      const draft = draftRef.current
      if (draft && draft.phase === 'pressing') {
        // 首锚点释放：拖拽位移达标直接成线，纯点击转等待第二下；工具保持激活可连续画线
        const t = releaseDraft(draft, { x: e.offsetX, y: e.offsetY })
        draftRef.current = t.session
        if (t.commit) {
          suppressClickRef.current = true
          commitDraft(t.commit)
        }
        sigRef.current = ''
        render()
      }
    }
    const onZrGlobalout = () => {
      const c = p.current.chart
      if (!c) return
      c.getZr().setCursorStyle('default')
      const draft = draftRef.current
      if (draft && draft.phase === 'pressing') {
        // 按住拖出画布：转等待第二下，不丢草稿
        draftRef.current = { ...draft, phase: 'awaitSecond' }
        sigRef.current = ''
        render()
      }
    }
    const onKeyDown = (ev: KeyboardEvent) => {
      const el = ev.target as HTMLElement | null
      if (el && ['INPUT', 'TEXTAREA'].includes(el.tagName)) return
      if (ev.key === 'Escape') {
        if (draftRef.current) {
          draftRef.current = null
          sigRef.current = ''
          render()
        } else if (p.current.selectedId) {
          p.current.onSelect(null)
        } else if (p.current.activeTool) {
          p.current.onRequestDisarm()
        } else if (p.current.onRequestExit) {
          p.current.onRequestExit()
        }
      } else if ((ev.key === 'Delete' || ev.key === 'Backspace') && p.current.selectedId) {
        p.current.onDelete(p.current.selectedId)
      }
    }

    chart.on('dataZoom', schedule)
    chart.on('resize', schedule)
    chart.on('finished', schedule)
    const zr = chart.getZr()
    zr.on('mousedown', onZrMouseDown as never)
    zr.on('click', onZrClick as never)
    zr.on('mousemove', onZrMousemove as never)
    zr.on('mouseup', onZrMouseup as never)
    zr.on('globalout', onZrGlobalout as never)
    window.addEventListener('keydown', onKeyDown)
    return () => {
      chart.off('dataZoom', schedule)
      chart.off('resize', schedule)
      chart.off('finished', schedule)
      zr.off('mousedown', onZrMouseDown as never)
      zr.off('click', onZrClick as never)
      zr.off('mousemove', onZrMousemove as never)
      zr.off('mouseup', onZrMouseup as never)
      zr.off('globalout', onZrGlobalout as never)
      window.removeEventListener('keydown', onKeyDown)
      if (zoomDisabledRef.current) {
        zoomDisabledRef.current = false
        try {
          const count = dataZoomCount(chart)
          if (count > 0) {
            chart.setOption({
              dataZoom: Array.from({ length: count }, () => ({ disabled: false })),
            } as EChartsOption)
          }
        } catch {
          /* 实例可能已 dispose */
        }
      }
      if (savedChromeRef.current) {
        const saved = savedChromeRef.current
        savedChromeRef.current = null
        try {
          chart.setOption({
            tooltip: { show: saved.tooltip },
            axisPointer: { show: saved.axisPointer },
          } as EChartsOption)
        } catch {
          /* 同上 */
        }
      }
      const ids = [...liveIdsRef.current]
      liveIdsRef.current = new Set()
      sigRef.current = ''
      dragRef.current = null
      draftRef.current = null
      try {
        if (ids.length && !chart.isDisposed()) {
          chart.setOption({ graphic: ids.map((id) => ({ id, $action: 'remove' })) } as EChartsOption)
        }
      } catch {
        /* 同上 */
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.chart])

  useEffect(() => {
    try {
      render()
    } catch (err) {
      console.warn('[drawing] 图层降级', err)
    }
  })

  return {
    getSelectedPixelPos: () => {
      const { chart, dates, selectedId, drawings } = p.current
      if (!chart || !selectedId) return null
      const d = drawings.find((item) => item.id === selectedId)
      if (!d || d.anchors.length === 0) return null
      return anchorToPx(chart, dates, d.anchors[0])
    },
  }
}
