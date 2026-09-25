/**
 * 画线图层重绘调度：sig 短路 → specs 收集（specCollector）→ 失活 remove →
 * safeSetOption 增量下发；armed 编辑态 chrome（dataZoom 互斥 + tooltip/axisPointer
 * 隐藏还原）在此收口。指针/键盘事件处理在 layerEvents.ts，hook 装配在
 * useDrawingLayer.ts；设计要点（docs/arch/05-web-frontend.md §5.3）见后者模块注。
 */

import type { MutableRefObject } from 'react'
import type { ECharts, EChartsOption } from 'echarts'

import { dataZoomCount, getMainGridRect, safeSetOption, viewFingerprint } from './chartInternals'
import type { CollectRefs } from './specCollector'
import { collectGraphicSpecs } from './specCollector'
import type { GraphicSpec } from './shapeSpecs'
import type { UseDrawingLayerParams } from './types'

/** 图层渲染态 refs（hook 持有，重绘调度消费） */
export interface LayerRefs extends CollectRefs {
  sigRef: MutableRefObject<string>
  zoomDisabledRef: MutableRefObject<boolean>
  /** armed 时被隐藏的主图浮层原状态（tooltip/axisPointer），退出时按原值还原 */
  savedChromeRef: MutableRefObject<{ tooltip: boolean; axisPointer: boolean } | null>
}

/** 增量渲染：merge-by-id + 失活 remove；被拖拽元素跳过重下发（zrender 原生移动中） */
export function renderLayer(p: { current: UseDrawingLayerParams }, refs: LayerRefs): void {
  const { chart, dates, drawings, aiDrawings, selectedId, activeTool, interactive } = p.current
  if (!chart || chart.isDisposed() || dates.length === 0) return
  const grid = getMainGridRect(chart)
  if (!grid) return

  const drag = refs.dragRef.current
  const draft = refs.draftRef.current
  const sig = JSON.stringify([drawings, aiDrawings, selectedId, activeTool, interactive, viewFingerprint(chart, dates), grid, draft, drag?.px])
  if (sig === refs.sigRef.current) return

  const { specs, nextIds } = collectGraphicSpecs(chart, p, refs, grid)
  const removed: GraphicSpec[] = []
  for (const id of refs.liveIdsRef.current) {
    if (!nextIds.has(id)) removed.push({ id, $action: 'remove' })
  }
  if (specs.length || removed.length) {
    // sig/liveIds 只在 setOption 成功后落地，失败时下一帧重试（否则整层冻结到刷新）
    if (!safeSetOption(chart, { graphic: [...specs, ...removed] })) {
      refs.sigRef.current = ''
      return
    }
  }
  refs.sigRef.current = sig
  refs.liveIdsRef.current = nextIds

  syncEditingChrome(chart, !!activeTool, refs)
}

/** armed 与全部 dataZoom 互斥（滚轮/拖动不缩放）；同时隐藏 K 线 tooltip/十字指示器，
 * 避免悬浮数据点压住画线预览（同花顺式编辑态） */
function syncEditingChrome(chart: ECharts, wantDisable: boolean, refs: LayerRefs): void {
  if (wantDisable !== refs.zoomDisabledRef.current) {
    const count = dataZoomCount(chart)
    if (count > 0) {
      chart.setOption({
        dataZoom: Array.from({ length: count }, () => ({ disabled: wantDisable })),
      } as EChartsOption)
    }
    refs.zoomDisabledRef.current = wantDisable
    try {
      if (wantDisable) {
        const opt = chart.getOption() as {
          tooltip?: { show?: boolean }
          axisPointer?: { show?: boolean }
        }
        refs.savedChromeRef.current = {
          tooltip: opt.tooltip?.show !== false,
          axisPointer: opt.axisPointer?.show !== false,
        }
        chart.setOption({ tooltip: { show: false }, axisPointer: { show: false } } as EChartsOption)
      } else if (refs.savedChromeRef.current) {
        const saved = refs.savedChromeRef.current
        refs.savedChromeRef.current = null
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
