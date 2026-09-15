/**
 * 画线图层指针/键盘事件处理器：草稿状态机推进、拖拽帧驱动、Esc/Delete 快捷键。
 * 工厂形式供 useDrawingLayer 的 effect 装配（bind/unbind 仍归 effect，处理逻辑归此处）。
 */

import type { MutableRefObject } from 'react'
import type { ECharts } from 'echarts'

import { dataZoomCount, isDrawingElement, getMainGridRect } from './chartInternals'
import { inRect, pxToAnchor } from './coordinates'
import { isTwoAnchorTool, moveDraft, pressSecond, releaseDraft, startDraft } from './draftMachine'
import type { DraftSession } from './draftMachine'
import type { DragSession } from './sessions'
import type { ZrEvent } from './shapeSpecs'
import { DRAWING_ROOT_PREFIX, type UseDrawingLayerParams } from './types'

/** 会话内唯一草稿 id 序列（固定 id 的孤儿子条目会被下一草稿按 id 复配到已移除的父组上） */
let draftSeq = 0

export interface LayerHandlersDeps {
  /** 最新参数（每次渲染同步，事件里只读） */
  p: { current: UseDrawingLayerParams }
  draftRef: MutableRefObject<DraftSession | null>
  /** 当前草稿会话的 graphic id 前缀（startDraft 时生成，会话内唯一） */
  draftIdRef: MutableRefObject<string>
  dragRef: MutableRefObject<DragSession | null>
  /** 成线提交后的 click 抑制（mousedown/mouseup 成线仍会派发一次 click，避免误清选中） */
  suppressClickRef: MutableRefObject<boolean>
  sigRef: MutableRefObject<string>
  render: () => void
  handleDragMove: (e: ZrEvent) => void
  finishDrag: () => void
  commitDraft: (pxs: { x: number; y: number }[]) => void
}

export function createLayerHandlers(deps: LayerHandlersDeps) {
  const { p, draftRef, draftIdRef, dragRef, suppressClickRef, sigRef } = deps
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
      if (t.commit) deps.commitDraft(t.commit)
      sigRef.current = ''
      deps.render()
      return
    }
    if (!draft && isTwoAnchorTool(activeTool)) {
      // 元素级交互优先（同花顺式）：点在已有画线/手柄上时不开新草稿，
      // 让选中/拖拽/锚点调整生效；点空白处才画新线。否则点旧线选不中、
      // 反而在原地多画一条默认样式的线（用户感知为"样式不生效/换色多线"）
      if (isDrawingElement(e.target)) return
      dragRef.current = null // 画线模式抢占元素级拖拽
      draftRef.current = startDraft(activeTool, pt)
      draftIdRef.current = `${DRAWING_ROOT_PREFIX}draft-${++draftSeq}`
      sigRef.current = ''
      deps.render()
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
    if (!grid) return
    if (activeTool) {
      // 双锚点工具成线由 mousedown/mouseup 状态机驱动；文字工具落点放宽到整个画布
      //（点击价格轴/时间轴附近也能标注，锚点换算自动吸附最近 bar）；
      // 其余单锚点工具单击即成线（限绘图区内）
      if (activeTool === 'text') {
        const pt = { x: e.offsetX, y: e.offsetY }
        p.current.onRequestTextInput({ px: pt, anchor: pxToAnchor(c, dates, pt) })
      } else if (inRect(e.offsetX, e.offsetY, grid) && !isTwoAnchorTool(activeTool)) {
        deps.commitDraft([{ x: e.offsetX, y: e.offsetY }])
      }
      return
    }
    if (!inRect(e.offsetX, e.offsetY, grid)) return
    if (e.target && isDrawingElement(e.target)) return // 元素级 onclick 已处理选中
    p.current.onSelect(null)
  }
  const onZrMousemove = (ev: unknown) => {
    const e = ev as ZrEvent
    const { chart: c, activeTool } = p.current
    // 编辑态强制十字光标（含悬在主图元素上时）
    if (c && activeTool && (!e.target || draftRef.current)) c.getZr().setCursorStyle('crosshair')
    if (dragRef.current) {
      deps.handleDragMove(e)
      return
    }
    if (draftRef.current) {
      const t = moveDraft(draftRef.current, { x: e.offsetX, y: e.offsetY })
      draftRef.current = t.session
      sigRef.current = ''
      deps.render()
    }
  }
  const onZrMouseup = (ev: unknown) => {
    if (dragRef.current) {
      deps.finishDrag()
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
        deps.commitDraft(t.commit)
      }
      sigRef.current = ''
      deps.render()
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
      deps.render()
    }
  }
  const onKeyDown = (ev: KeyboardEvent) => {
    const el = ev.target as HTMLElement | null
    if (el && ['INPUT', 'TEXTAREA'].includes(el.tagName)) return
    if (ev.key === 'Escape') {
      if (draftRef.current) {
        draftRef.current = null
        sigRef.current = ''
        deps.render()
      } else if (p.current.selectedId) {
        p.current.onSelect(null)
      } else if (p.current.activeTool) {
        p.current.onRequestDisarm()
      } else if (p.current.onRequestExit) {
        p.current.onRequestExit()
      }
    } else if ((ev.key === 'Delete' || ev.key === 'Backspace') && p.current.selectedId) {
      const selectedId = p.current.selectedId
      if (selectedId.startsWith('ai:')) {
        const item = p.current.aiDrawings.find((it) => `ai:${it.id}` === selectedId)
        if (item) p.current.onDeleteAiItem(item.label)
        p.current.onSelect(null)
      } else {
        p.current.onDelete(selectedId)
      }
    }
  }
  return { onZrMouseDown, onZrClick, onZrMousemove, onZrMouseup, onZrGlobalout, onKeyDown }
}

/** teardown 时还原 armed 态副作用：dataZoom 解禁 + 主图浮层还原 + 整层 graphic 擦除 */
export function teardownLayerState(
  chart: ECharts,
  refs: {
    zoomDisabledRef: MutableRefObject<boolean>
    savedChromeRef: MutableRefObject<{ tooltip: boolean; axisPointer: boolean } | null>
    liveIdsRef: MutableRefObject<Set<string>>
    sigRef: MutableRefObject<string>
    dragRef: MutableRefObject<DragSession | null>
    draftRef: MutableRefObject<DraftSession | null>
  },
) {
  const { zoomDisabledRef, savedChromeRef, liveIdsRef, sigRef, dragRef, draftRef } = refs
  if (zoomDisabledRef.current) {
    zoomDisabledRef.current = false
    try {
      const count = dataZoomCount(chart)
      if (count > 0) {
        chart.setOption({ dataZoom: Array.from({ length: count }, () => ({ disabled: false })) } as never)
      }
    } catch {
      /* 实例可能已 dispose */
    }
  }
  if (savedChromeRef.current) {
    const saved = savedChromeRef.current
    savedChromeRef.current = null
    try {
      chart.setOption({ tooltip: { show: saved.tooltip }, axisPointer: { show: saved.axisPointer } } as never)
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
      chart.setOption({ graphic: ids.map((id) => ({ id, $action: 'remove' })) } as never)
    }
  } catch {
    /* 同上 */
  }
}

