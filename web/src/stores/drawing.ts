/**
 * 画线交互状态（arch/05 §5.3）：当前工具 / 选中项 / AI 图层显隐；
 * 默认样式记忆 localStorage（per user 跟随登录态）。
 */

import { StorageKey } from '@ai-invest/shared'
import type { KlineDrawingStyle, KlineDrawingType } from '@ai-invest/shared'
import { create } from 'zustand'

export const DRAWING_COLORS = [
  '#f0b429',
  '#e35d6a',
  '#3fb6e0',
  '#22c55e',
  '#a855f7',
  '#e8833a',
] as const

const DEFAULT_STYLE: KlineDrawingStyle = { color: DRAWING_COLORS[0], lineStyle: 'solid', width: 2 }

const getStoredDefaultStyle = (): KlineDrawingStyle => {
  try {
    const raw = localStorage.getItem(StorageKey.drawing.defaultStyle)
    if (!raw) return DEFAULT_STYLE
    const parsed = JSON.parse(raw) as Partial<KlineDrawingStyle>
    return {
      color: parsed.color ?? DEFAULT_STYLE.color,
      lineStyle: parsed.lineStyle ?? DEFAULT_STYLE.lineStyle,
      width: (parsed.width === 1 || parsed.width === 3 ? parsed.width : 2) as KlineDrawingStyle['width'],
    }
  } catch {
    return DEFAULT_STYLE
  }
}

interface DrawingState {
  /** 画线工具（null = 光标模式） */
  activeTool: KlineDrawingType | null
  selectedId: string | null
  userLayerVisible: boolean
  aiLayerVisible: boolean
  /** 画线清单面板显隐 */
  panelOpen: boolean
  /** 画线编辑态（图表左缘竖排工具栏可见） */
  toolbarOpen: boolean
  /** 新画线默认样式（记忆值） */
  defaultStyle: KlineDrawingStyle

  setActiveTool: (tool: KlineDrawingType | null) => void
  select: (id: string | null) => void
  toggleUserLayer: () => void
  toggleAiLayer: () => void
  togglePanel: () => void
  enterDrawing: () => void
  exitDrawing: () => void
  setDefaultStyle: (style: Partial<KlineDrawingStyle>) => void
}

export const useDrawingStore = create<DrawingState>((set) => ({
  activeTool: null,
  selectedId: null,
  userLayerVisible: true,
  aiLayerVisible: true,
  panelOpen: false,
  toolbarOpen: false,
  defaultStyle: getStoredDefaultStyle(),

  setActiveTool: (tool) => set({ activeTool: tool, selectedId: null }),
  select: (id) => set({ selectedId: id }),
  toggleUserLayer: () => set((s) => ({ userLayerVisible: !s.userLayerVisible })),
  toggleAiLayer: () => set((s) => ({ aiLayerVisible: !s.aiLayerVisible })),
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  enterDrawing: () => set({ toolbarOpen: true }),
  exitDrawing: () => set({ toolbarOpen: false, activeTool: null, selectedId: null }),
  setDefaultStyle: (style) =>
    set((s) => {
      const next = { ...s.defaultStyle, ...style }
      try {
        localStorage.setItem(StorageKey.drawing.defaultStyle, JSON.stringify(next))
      } catch {
        /* 存储满等异常不阻断交互 */
      }
      return { defaultStyle: next }
    }),
}))
