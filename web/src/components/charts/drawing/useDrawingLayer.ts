/**
 * 画线图层生命周期 hook：渲染主循环 + effect 装配；指针/键盘事件处理在 layerEvents.ts，
 * 参数类型在 types.ts（前端单一真相源）。
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

import type { EChartsOption } from 'echarts'
import { useEffect, useRef } from 'react'

import { dataZoomCount, getMainGridRect, getZrEl, safeSetOption, viewFingerprint } from './chartInternals'
import { anchorToPx, drawingPx, pxToAnchor } from './coordinates'
import type { DraftSession } from './draftMachine'
import { createLayerHandlers, teardownLayerState } from './layerEvents'
import {
  aiElementIds,
  aiHandleElementIds,
  aiHandleSpecs,
  aiSpecs,
  type DragHooks,
  type GraphicSpec,
  draftSpecs,
  handleElementIds,
  handleSpecs,
  userElementIds,
  userShapeSpecs,
  type ZrEvent,
} from './shapeSpecs'
import {
  type DragSession,
  applyDragMove,
  dragAnchors,
  dragMoved,
  startAiDrag,
  startUserDrag,
} from './sessions'
import { DRAWING_ROOT_PREFIX, type Point, type UseDrawingLayerParams } from './types'

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
    const { chart, dates, drawings, onUpdate, onUpdateAiItem } = p.current
    if (!chart) return
    if (drag.ai) {
      const item = p.current.aiDrawings.find((it) => it.label === drag.ai?.label)
      onUpdateAiItem(drag.ai.label, {
        anchors: dragAnchors(drag, chart, dates, item?.drawingType === 'hline'),
      })
      return
    }
    const omitDate = drawings.find((d) => d.id === drag.drawingId)?.drawingType === 'hline'
    onUpdate(drag.drawingId, {
      anchors: dragAnchors(drag, chart, dates, omitDate),
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
    const sig = JSON.stringify([drawings, aiDrawings, selectedId, activeTool, interactive, viewFingerprint(chart, dates), grid, draft, drag?.px])
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
      // 整体拖拽中手柄不参与原生移动，按实时 px 重下发跟随；锚点拖拽中手柄是原生移动方，
      // 必须保活——从 storage 移除会让下一帧 hover 落空（target 变主图元素），拖拽即断
      if (interactive && selectedId === d.id) {
        if (!dragHere || drag?.kind === 'move') {
          track(handleSpecs(d, pxNow, live))
        } else {
          for (const id of handleElementIds(d)) {
            if (liveIdsRef.current.has(id)) nextIds.add(id)
          }
        }
      }
    }
    for (const item of aiDrawings) {
      const aiDrag = drag?.ai?.label === item.label ? drag : null
      const aiPxNow = aiDrag && aiDrag.kind === 'anchor' ? aiDrag.px : item.anchors.map((a) => anchorToPx(chart, dates, a))
      const live: DragHooks = {
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
      // 整体拖拽中元素由 zrender 原生移动 + 兄弟镜像，跳过重下发（同用户画线）
      if (!aiDrag || aiDrag.kind === 'anchor') {
        track(aiSpecs(item, aiPxNow, grid, () => {}, interactive && !aiDrag, live))
      } else {
        for (const id of aiElementIds(item)) {
          if (liveIdsRef.current.has(id)) nextIds.add(id)
        }
      }
      if (interactive && selectedId === `ai:${item.id}`) {
        if (!aiDrag || aiDrag.kind === 'move') {
          track(aiHandleSpecs(item, aiPxNow, live))
        } else {
          for (const id of aiHandleElementIds(item)) {
            if (liveIdsRef.current.has(id)) nextIds.add(id)
          }
        }
      }
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
      // sig/liveIds 只在 setOption 成功后落地，失败时下一帧重试（否则整层冻结到刷新）
      if (!safeSetOption(chart, { graphic: [...specs, ...removed] })) {
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
    dragRef.current = applyDragMove(drag, e.target, p.current.chart)
    try {
      render()
    } catch (err) {
      console.warn('[drawing] 图层降级', err)
    }
  }

  useEffect(() => {
    const chart = params.chart
    // 非空但已 dispose 的实例同样不可绑定：切股时宿主图表分支可能闪挂，
    // onChartReady 触发 setState 后、effect 执行前实例已被销毁（getZr() 为 null），
    // 仅判 !chart 挡不住——echarts 级 on/off 在已销毁实例上不报错，zr 级绑定会崩
    if (!chart || chart.isDisposed() || !chart.getZr()) return
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
    const { onZrMouseDown, onZrClick, onZrMousemove, onZrMouseup, onZrGlobalout, onKeyDown } =
      createLayerHandlers({
        p,
        draftRef,
        draftIdRef,
        dragRef,
        suppressClickRef,
        sigRef,
        render,
        handleDragMove,
        finishDrag,
        commitDraft,
      })

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
      // 卸载与 dispose 存在竞态（宿主图表分支闪挂时实例先被销毁），
      // teardown 全程容错：解绑失败不向上抛（此前渲染期崩溃的另一条路径）
      try {
        chart.off('dataZoom', schedule)
        chart.off('resize', schedule)
        chart.off('finished', schedule)
        zr.off('mousedown', onZrMouseDown as never)
        zr.off('click', onZrClick as never)
        zr.off('mousemove', onZrMousemove as never)
        zr.off('mouseup', onZrMouseup as never)
        zr.off('globalout', onZrGlobalout as never)
        window.removeEventListener('keydown', onKeyDown)
        teardownLayerState(chart, {
          zoomDisabledRef,
          savedChromeRef,
          liveIdsRef,
          sigRef,
          dragRef,
          draftRef,
        })
      } catch {
        /* 实例已 dispose 的卸载竞态：解绑失败不向上抛 */
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
      // 宿主在渲染期调用本函数取样式条定位：已 dispose 的实例必须返回 null
      //（convertToPixel 会抛错，渲染期抛错即整页崩溃页），分支闪挂竞态同绑定守卫
      if (!chart || !selectedId || chart.isDisposed() || !chart.getZr()) return null
      const d = drawings.find((item) => item.id === selectedId)
      if (!d || d.anchors.length === 0) return null
      return anchorToPx(chart, dates, d.anchors[0])
    },
  }
}
