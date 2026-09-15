/**
 * K 线数据准备：bar 序列 → 指标齐备的图表数据（KlineChartData）。
 * 纯数据变换，不感知 ECharts option 结构（主装配见 klineOption.ts）。
 */

import { calculateKDJ, calculateMACD } from '@/utils/indicators'
import { movingAverage } from '@/utils/movingAverage'
import type { MovingAverageConfig, StockKlineBar } from '@ai-invest/shared'

export interface KlineChartData {
  dates: string[]
  bars: StockKlineBar[]
  opens: number[]
  closes: number[]
  highs: number[]
  lows: number[]
  volumes: number[]
  mas: { period: number; color: string; values: (number | null)[] }[]
  macd: ReturnType<typeof calculateMACD>
  kdj: ReturnType<typeof calculateKDJ>
}

export function prepareKlineData(
  kline: { bars: StockKlineBar[] },
  maConfigs: MovingAverageConfig[],
): KlineChartData {
  const bars = kline.bars
  const dates = bars.map((b) => b.date)
  const opens = bars.map((b) => b.open)
  const closes = bars.map((b) => b.close)
  const highs = bars.map((b) => b.high)
  const lows = bars.map((b) => b.low)
  const volumes = bars.map((b) => b.volume)

  const mas = maConfigs
    .filter((cfg) => cfg.enabled)
    .map((cfg) => ({
      period: cfg.period,
      color: cfg.color,
      values: movingAverage(closes, cfg.period),
    }))

  return {
    dates,
    bars,
    opens,
    closes,
    highs,
    lows,
    volumes,
    mas,
    macd: calculateMACD(closes),
    kdj: calculateKDJ(highs, lows, closes),
  }
}
