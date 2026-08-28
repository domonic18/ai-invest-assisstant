import { panelColors } from '@/theme/colors'

export const PERIOD_OPTIONS = [
  { label: '分时', value: 'intraday' },
  { label: '日线', value: 'daily' },
  { label: '周线', value: 'weekly' },
  { label: '月线', value: 'monthly' },
]

export const MA_CONFIGS = [
  { period: 5, color: '#f59e0b' },
  { period: 10, color: '#3b82f6' },
  { period: 20, color: '#a855f7' },
  { period: 60, color: '#22c55e' },
]

export const PANEL_BG = panelColors.bg
export const BORDER_COLOR = panelColors.border
export const TEXT_MUTED = panelColors.textMuted
export const TEXT_MAIN = '#d1d4dc'
export const GRID_COLOR = '#1f2229'
