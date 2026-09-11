import type { StockChartViewIndicators } from '@/components/charts/stockChartView/StockChartView'

/** 板块指数周期：仅 日K/周K（无分时/月线源，周线由日线客户端聚合）。 */
export const SECTOR_PERIOD_OPTIONS = [
  { label: '日K', value: 'daily' },
  { label: '周K', value: 'weekly' },
]

export const DEFAULT_SECTOR_INDICATORS: StockChartViewIndicators = {
  volume: true,
  ma: true,
  macd: false,
  kdj: false,
}

/** 双图加权分配：上（日线）58 / 下（周线）42，与个股详情一致。 */
export const DUAL_VIEW_WEIGHTS = [0.58, 0.42]
export const MIN_CHART_HEIGHT = 180
