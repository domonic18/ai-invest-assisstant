import { create } from 'zustand'

/**
 * K 线视图跨股票会话布局：在个股间切换时继承单/双图、各视图 K 线周期与
 * 键盘缩放窗口（上/下视图各记各的，按视图槽位 id 键控）。
 *
 * 仅会话内生效、不落盘（沿用「双图持久化会把用户锁在双图」的既有决策）；
 * per-stock localStorage 仍只承载指标等偏好，周期在会话内以本 store 为准。
 */

/** 缩放窗口的可继承形态：span=可见 bar 数，endOffset=窗口右端距最新 bar 的偏移（0=贴最新）。 */
export interface KlineZoomWindowState {
  span: number
  endOffset: number
}

/**
 * 会话记忆的缩放窗口映射到新数据：span 超过总 bar 数收缩到全长，
 * 右端按 endOffset 锚定最新 bar，越界（回看得比数据还早）则贴左缘。
 */
export function resolveZoomWindow(
  saved: KlineZoomWindowState,
  barCount: number,
): { start: number; end: number } {
  const last = Math.max(0, barCount - 1)
  const span = Math.max(1, Math.min(saved.span, barCount))
  let end = last - Math.max(0, saved.endOffset)
  if (end < span - 1) end = span - 1
  const start = Math.max(0, end - span + 1)
  return { start, end: Math.max(start, end) }
}

interface KlineViewLayoutState {
  dual: boolean
  periods: Record<string, string>
  windows: Record<string, KlineZoomWindowState>
  setDual: (dual: boolean) => void
  setPeriod: (viewId: string, period: string) => void
  setWindow: (viewId: string, window: KlineZoomWindowState) => void
}

export const useKlineViewLayoutStore = create<KlineViewLayoutState>((set) => ({
  dual: false,
  periods: {},
  windows: {},
  setDual: (dual) => set({ dual }),
  setPeriod: (viewId, period) =>
    set((s) => ({ periods: { ...s.periods, [viewId]: period } })),
  setWindow: (viewId, window) =>
    set((s) => ({ windows: { ...s.windows, [viewId]: window } })),
}))
