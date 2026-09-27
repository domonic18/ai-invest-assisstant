/**
 * 画线图层生命周期 hook：refs 持有 + effect 装配；重绘调度在 layerRender.ts，
 * specs 收集与拖拽钩子构造在 specCollector.ts，指针/键盘事件处理在 layerEvents.ts，
 * 参数类型在 types.ts（前端单一真相源）。
 *
 * 设计要点（docs/arch/05-web-frontend.md §5.3）：
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

import { useEffect, useRef } from 'react'

import { getZrEl } from './chartInternals'
import { anchorToPx, pxToAnchor } from './coordinates'
import type { DraftSession } from './draftMachine'
import { createLayerHandlers, teardownLayerState } from './layerEvents'
import type { LayerRefs } from './layerRender'
import { renderLayer } from './layerRender'
import type { ZrEvent } from './shapeSpecs'
import type { DragSession } from './sessions'
import { applyDragMove, dragAnchors, dragMoved } from './sessions'
import type { Point, UseDrawingLayerParams } from './types'

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

  const refs: LayerRefs = { draftRef, draftIdRef, dragRef, sigRef, liveIdsRef, zoomDisabledRef, savedChromeRef }

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

  /** zrender 拖拽实时移动：被抓元素原生位移，兄弟元素镜像 + 像素锚点重算 */
  const handleDragMove = (e: ZrEvent) => {
    const drag = dragRef.current
    if (!drag) return
    dragRef.current = applyDragMove(drag, e.target, p.current.chart)
    try {
      renderLayer(p, refs)
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
        renderLayer(p, refs)
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
        render: () => renderLayer(p, refs),
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
      renderLayer(p, refs)
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
