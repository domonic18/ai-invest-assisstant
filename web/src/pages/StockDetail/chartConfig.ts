import type { StockChartViewIndicators } from '@/components/charts/stockChartView'

export const STORAGE_KEY = 'ai-invest.stock-detail.views'

export const TOOLBAR_HEIGHT = 68
export const MIN_CHART_HEIGHT = 180

export const DEFAULT_INDICATORS: StockChartViewIndicators = {
  volume: true,
  ma: true,
  macd: false,
  kdj: false,
}

export interface ChartViewConfig {
  id: string
  period: string
  indicators: StockChartViewIndicators
}

export type ViewPresetKey = 'daily-weekly' | 'daily-monthly' | 'daily' | 'weekly'

export interface ViewPreset {
  key: ViewPresetKey
  label: string
  views: ChartViewConfig[]
}

export const VIEW_PRESETS: ViewPreset[] = [
  {
    key: 'daily-weekly',
    label: '日线 + 周线',
    views: [
      { id: 'daily', period: 'daily', indicators: { ...DEFAULT_INDICATORS } },
      { id: 'weekly', period: 'weekly', indicators: { ...DEFAULT_INDICATORS } },
    ],
  },
  {
    key: 'daily-monthly',
    label: '日线 + 月线',
    views: [
      { id: 'daily', period: 'daily', indicators: { ...DEFAULT_INDICATORS } },
      { id: 'monthly', period: 'monthly', indicators: { ...DEFAULT_INDICATORS } },
    ],
  },
  {
    key: 'daily',
    label: '仅日线',
    views: [{ id: 'daily', period: 'daily', indicators: { ...DEFAULT_INDICATORS } }],
  },
  {
    key: 'weekly',
    label: '仅周线',
    views: [{ id: 'weekly', period: 'weekly', indicators: { ...DEFAULT_INDICATORS } }],
  },
]

export function findPresetKey(views: ChartViewConfig[]): ViewPresetKey | 'custom' {
  for (const preset of VIEW_PRESETS) {
    if (
      views.length === preset.views.length &&
      views.every((v, i) => v.period === preset.views[i].period)
    ) {
      return preset.key
    }
  }
  return 'custom'
}
