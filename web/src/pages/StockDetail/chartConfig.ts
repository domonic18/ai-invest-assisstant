import {
  CHROME_HEIGHT,
  type StockChartViewIndicators,
} from '@/components/charts/stockChartView'

export const STORAGE_KEY = 'ai-invest.stock-detail.views.v2'

export const TOOLBAR_HEIGHT = CHROME_HEIGHT + 2
export const MIN_CHART_HEIGHT = 180

export const DEFAULT_INDICATORS: StockChartViewIndicators = {
  volume: true,
  ma: true,
  macd: false,
  kdj: false,
}

function withIndicators(
  overrides: Partial<StockChartViewIndicators> = {},
): StockChartViewIndicators {
  return { ...DEFAULT_INDICATORS, ...overrides }
}

export interface ChartViewConfig {
  id: string
  period: string
  indicators: StockChartViewIndicators
}

/** 双图 = 日K(52%) + 周K(42%)，单图 = 仅日K；周期组合与原型固定，不提供下拉切换。 */
export function buildViews(dual: boolean): ChartViewConfig[] {
  const daily: ChartViewConfig = {
    id: 'daily',
    period: 'daily',
    indicators: withIndicators({ macd: true }),
  }
  if (!dual) return [daily]
  const weekly: ChartViewConfig = {
    id: 'weekly',
    period: 'weekly',
    indicators: withIndicators(),
  }
  return [daily, weekly]
}
