import { create } from 'zustand'

const STORAGE_KEY = 'ai-invest.sidebar.v1'

/** 折叠态宽度与 antd 折叠菜单默认宽度(80px)对齐。 */
export const SIDEBAR_COLLAPSED_WIDTH = 80
export const SIDEBAR_DEFAULT_WIDTH = 224 // 对齐 w-56
export const SIDEBAR_MIN_WIDTH = 180
export const SIDEBAR_MAX_WIDTH = 420

export function clampSidebarWidth(width: number): number {
  return Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, Math.round(width)))
}

interface SidebarPrefs {
  collapsed: boolean
  width: number
}

function readPrefs(): SidebarPrefs {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<SidebarPrefs>
      return {
        collapsed: parsed.collapsed === true,
        width: clampSidebarWidth(Number(parsed.width) || SIDEBAR_DEFAULT_WIDTH),
      }
    }
  } catch {
    // ignore malformed storage
  }
  return { collapsed: false, width: SIDEBAR_DEFAULT_WIDTH }
}

interface SidebarState extends SidebarPrefs {
  toggleCollapsed: () => void
  setWidth: (width: number) => void
}

function persist(state: SidebarPrefs): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch {
    // ignore storage errors
  }
}

export const useSidebarStore = create<SidebarState>()((set, get) => ({
  ...readPrefs(),
  toggleCollapsed: () => {
    set({ collapsed: !get().collapsed })
    persist(get())
  },
  setWidth: (width) => {
    const next = clampSidebarWidth(width)
    if (next === get().width) return
    set({ width: next })
    persist(get())
  },
}))
