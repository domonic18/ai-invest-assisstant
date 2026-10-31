import { panelColors } from '@/theme/colors'

export const PERIOD_OPTIONS = [
  { label: '分时', value: 'intraday' },
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
  { label: '月K', value: 'monthly' },
]

export const PANEL_BG = panelColors.bg
export const BORDER_COLOR = panelColors.border
export const TEXT_MUTED = panelColors.textMuted
export const TEXT_MAIN = '#d1d4dc'
export const GRID_COLOR = '#1f2229'

/** 个股/板块 K 线所有 grid 共享的左右边界（对齐契约，见 chartLayout.ts）。 */
export const STOCK_GRID_EDGES = { left: 46, right: 60 } as const
