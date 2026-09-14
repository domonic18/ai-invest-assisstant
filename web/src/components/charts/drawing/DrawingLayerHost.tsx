/**
 * 画线图层集成宿主：组合数据 hooks + drawingStore + useDrawingLayer + StyleBar。
 * 图表组件以声明式接入（arch/09 §3.2「组合方式接入」），本身不渲染主图。
 */

import type { ECharts } from 'echarts'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { EyeInvisibleOutlined, EyeOutlined } from '@ant-design/icons'
import { message } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { PAGE_EVENT_TYPES } from '@ai-invest/shared'
import type { KlineDrawingPeriod, KlineDrawingTargetType } from '@ai-invest/shared'

import {
  useAdoptAiDrawing,
  useClearAiDrawings,
  useCreateKlineDrawing,
  useDeleteAiDrawingItem,
  useDeleteKlineDrawing,
  useKlineDrawings,
  useUpdateAiDrawingItem,
  useUpdateKlineDrawing,
} from '@/hooks/useKlineDrawings'
import { usePageAssistantResult } from '@/hooks/usePageAssistantResult'
import { queryKeys } from '@/hooks/queryKeys'
import { useDrawingStore } from '@/stores/drawing'
import type { KlineDrawingResult } from '@/stores/assistant'

import { useDrawingLayer, type DrawingTextEditRequest } from './useDrawingLayer'
import { DrawingsPanel } from './DrawingsPanel'
import { DrawingSideBar } from './DrawingSideBar'
import { DrawingTextInput } from './DrawingTextInput'
import { StyleBar } from './StyleBar'
import { DRAWING_TOOL_HINTS, DRAWING_TYPE_LABEL } from './types'

export interface DrawingTarget {
  targetType: KlineDrawingTargetType
  targetCode: string
}

interface DrawingLayerHostProps {
  /** echarts-for-react 实例（onChartReady 捕获） */
  chart: ECharts | null
  /** 主图 category x 轴日期序列 */
  dates: string[]
  target: DrawingTarget
  period: KlineDrawingPeriod
}

export function DrawingLayerHost({ chart, dates, target, period }: DrawingLayerHostProps) {
  const { targetType, targetCode } = target
  const { data } = useKlineDrawings(targetType, targetCode)
  const activeTool = useDrawingStore((s) => s.activeTool)
  const selectedId = useDrawingStore((s) => s.selectedId)
  const defaultStyle = useDrawingStore((s) => s.defaultStyle)
  const userLayerVisible = useDrawingStore((s) => s.userLayerVisible)
  const aiLayerVisible = useDrawingStore((s) => s.aiLayerVisible)
  const panelOpen = useDrawingStore((s) => s.panelOpen)
  const toolbarOpen = useDrawingStore((s) => s.toolbarOpen)
  const toggleUserLayer = useDrawingStore((s) => s.toggleUserLayer)
  const toggleAiLayer = useDrawingStore((s) => s.toggleAiLayer)
  const exitDrawing = useDrawingStore((s) => s.exitDrawing)
  const setActiveTool = useDrawingStore((s) => s.setActiveTool)
  const select = useDrawingStore((s) => s.select)
  const setDefaultStyle = useDrawingStore((s) => s.setDefaultStyle)

  const create = useCreateKlineDrawing(targetType, targetCode)
  const update = useUpdateKlineDrawing(targetType, targetCode)
  const remove = useDeleteKlineDrawing(targetType, targetCode)
  const adopt = useAdoptAiDrawing(targetType, targetCode)
  const updateAi = useUpdateAiDrawingItem(targetType, targetCode)
  const deleteAi = useDeleteAiDrawingItem(targetType, targetCode)
  const clearAi = useClearAiDrawings(targetType, targetCode)

  /** 文字标注输入框状态（文字工具点击落点弹出 / 双击已有文字进入编辑） */
  const [textEdit, setTextEdit] = useState<DrawingTextEditRequest | null>(null)
  useEffect(() => {
    if (!toolbarOpen) setTextEdit(null)
  }, [toolbarOpen])

  const submitText = (value: string) => {
    const text = value.trim()
    setTextEdit(null)
    if (!textEdit || !text) return
    if (textEdit.aiLabel) {
      updateAi.mutate({ targetType, targetCode, period, label: textEdit.aiLabel, newLabel: text })
    } else if (textEdit.drawingId) {
      update.mutate({ id: textEdit.drawingId, data: { text } })
    } else if (textEdit.anchor) {
      create.mutate({
        targetType,
        targetCode,
        period,
        drawingType: 'text',
        anchors: [textEdit.anchor],
        style: defaultStyle,
        text,
      })
    }
  }

  const userDrawings = useMemo(
    () => (data?.user ?? []).filter((d) => d.period === period),
    [data, period],
  )
  // AI 组展平为稳定 id 画线（period + label 组内唯一 → id 稳定不闪动）
  const aiItems = useMemo(
    () =>
      (data?.ai ?? [])
        .filter((g) => g.period === period)
        .flatMap((g) => g.drawings.map((item) => ({ ...item, id: `${period}:${item.label}` }))),
    [data, period],
  )

  const { getSelectedPixelPos } = useDrawingLayer({
    chart,
    dates,
    scope: { targetType, targetCode, period },
    drawings: userLayerVisible ? userDrawings : [],
    aiDrawings: aiLayerVisible ? aiItems : [],
    activeTool,
    selectedId,
    defaultStyle,
    interactive: toolbarOpen,
    onCreate: (req) => create.mutate(req),
    onUpdate: (id, patch) => update.mutate({ id, data: patch }),
    onSelect: select,
    onDelete: (id) => {
      remove.mutate(id)
      if (selectedId === id) select(null)
    },
    onUpdateAiItem: (label, patch) => updateAi.mutate({ targetType, targetCode, period, label, ...patch }),
    onDeleteAiItem: (label) => {
      deleteAi.mutate({ targetType, targetCode, period, label })
      select(null)
    },
    onRequestDisarm: () => setActiveTool(null),
    onRequestExit: exitDrawing,
    onRequestTextInput: setTextEdit,
  })

  // 样式条挂在选中画线首锚点附近（坐标系与图表容器一致）
  const selected = userDrawings.find((d) => d.id === selectedId)
  const anchorPx = selected ? getSelectedPixelPos() : null

  // AI 画线完成事件：标的匹配本页时刷新画线数据（其余标的留给目标页消费）
  const queryClient = useQueryClient()
  const onDrawingComplete = useCallback(
    (result: KlineDrawingResult) => {
      if (result.targetType !== targetType || result.targetCode !== targetCode) return false
      void queryClient.invalidateQueries({ queryKey: queryKeys.klineDrawings.target(targetType, targetCode) })
      void message.success(`AI 已画 ${result.count} 条线，可拖拽调整/双击改名/清单采纳`)
      return true
    },
    [queryClient, targetType, targetCode],
  )
  usePageAssistantResult(PAGE_EVENT_TYPES.klineDrawing, onDrawingComplete)

  // 清单面板数据（AI 按组展示，含组 summary 与来源）
  const periodAiGroups = useMemo(
    () => (data?.ai ?? []).filter((g) => g.period === period),
    [data, period],
  )

  return (
    <>
      {toolbarOpen && (
        <DrawingSideBar
          hasSelection={!!selectedId}
          onDeleteSelected={() => {
            if (!selectedId) return
            remove.mutate(selectedId)
            select(null)
          }}
        />
      )}
      {activeTool && (
        <div className="pointer-events-none absolute left-1/2 top-1.5 z-20 -translate-x-1/2 whitespace-nowrap rounded-full border border-[#5e6ad2]/40 bg-[#1a1d24]/90 px-3 py-0.5 text-[11px] leading-[18px] text-[#aeb4ff]">
          画线中 · {DRAWING_TYPE_LABEL[activeTool]}：{DRAWING_TOOL_HINTS[activeTool]} · Esc 退出绘制
        </div>
      )}
      {textEdit && (
        <DrawingTextInput
          position={{ left: textEdit.px.x, top: textEdit.px.y }}
          bounds={{ width: chart?.getWidth() ?? 0, height: chart?.getHeight() ?? 0 }}
          initial={textEdit.initial}
          onSubmit={submitText}
          onCancel={() => setTextEdit(null)}
        />
      )}
      {panelOpen && (
        <div className="absolute top-9 right-2 z-20 max-h-[85%] w-72 overflow-auto rounded-md border border-white/10 bg-[#1a1d24]/95 p-2.5 shadow-lg">
          <div className="mb-1.5 flex items-center justify-between gap-2 border-b border-white/10 pb-1.5">
            <span className="text-xs font-medium text-[#c9cdd4]">画线清单</span>
            <span className="flex items-center gap-1.5">
              <button
                type="button"
                className={userLayerVisible ? 'text-[#9aa0aa]' : 'text-[#5a5f6a]'}
                title={userLayerVisible ? '隐藏用户画线' : '显示用户画线'}
                onClick={toggleUserLayer}
              >
                {userLayerVisible ? <EyeOutlined /> : <EyeInvisibleOutlined />}
              </button>
              <button
                type="button"
                className={aiLayerVisible ? 'text-[#9aa0aa]' : 'text-[#5a5f6a]'}
                title={aiLayerVisible ? '隐藏 AI 画线' : '显示 AI 画线'}
                onClick={toggleAiLayer}
              >
                {aiLayerVisible ? <EyeOutlined /> : <EyeInvisibleOutlined />}
              </button>
            </span>
          </div>
          <DrawingsPanel
            drawings={userDrawings}
            aiGroups={periodAiGroups}
            selectedId={selectedId}
            onSelect={select}
            onDelete={(id) => {
              remove.mutate(id)
              if (selectedId === id) select(null)
            }}
            onAdopt={({ label, period: p }) =>
              adopt.mutate({
                targetType,
                targetCode,
                period: p,
                label,
                style: defaultStyle,
              })
            }
            onClearAi={(p) => clearAi.mutate({ targetType, targetCode, period: p })}
          />
        </div>
      )}
      {selected && anchorPx && (
        <StyleBar
          drawing={selected}
          position={{ left: Math.max(8, anchorPx.x - 24), top: anchorPx.y + 14 }}
          bounds={{ width: chart?.getWidth() ?? 0, height: chart?.getHeight() ?? 0 }}
          onPatch={(patch) => {
            if (patch.style) setDefaultStyle(patch.style)
            update.mutate({ id: selected.id, data: patch })
          }}
          onDelete={() => {
            remove.mutate(selected.id)
            select(null)
          }}
        />
      )}
    </>
  )
}
