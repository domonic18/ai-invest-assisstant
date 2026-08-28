export const MIN_SIDEBAR_WIDTH = 220
export const MAX_SIDEBAR_WIDTH = 400
export const DEFAULT_SIDEBAR_WIDTH = 260
export const SIDEBAR_STORAGE_KEY = 'assistant-sidebar-width'

export const MIN_DRAWER_WIDTH = 520
export const MAX_DRAWER_WIDTH = 960
export const DEFAULT_DRAWER_WIDTH = 760
export const DRAWER_STORAGE_KEY = 'assistant-drawer-width'

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export function readStoredWidth(
  key: string,
  defaultValue: number,
  min: number,
  max: number,
): number {
  if (typeof window === 'undefined') return defaultValue
  const raw = window.localStorage.getItem(key)
  const value = raw ? Number.parseInt(raw, 10) : NaN
  return Number.isFinite(value) ? clamp(value, min, max) : defaultValue
}
