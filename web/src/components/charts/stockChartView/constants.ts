import { panelColors } from '@/theme/colors'

export const PERIOD_OPTIONS = [
  { label: '分时', value: 'intraday' },
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
  { label: '月K', value: 'monthly' },
]

export const MA_CONFIGS = [
  { period: 5, color: '#f85149' },
  { period: 10, color: '#d29922' },
  { period: 20, color: '#58a6ff' },
  { period: 60, color: '#a371f7' },
]

export const PANEL_BG = panelColors.bg
export const BORDER_COLOR = panelColors.border
export const TEXT_MUTED = panelColors.textMuted
export const TEXT_MAIN = '#d1d4dc'
export const GRID_COLOR = '#1f2229'
