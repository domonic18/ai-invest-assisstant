/**
 * K 线 dataZoom 联动（StockChartView / SectorKlineView 共用）：
 * 双击复位默认窗口 + 缩放（键盘 ↑/↓、滚轮、滑块）后按可见窗口重算主图纵轴，对齐同花顺行为。
 */

import type { RefObject } from 'react'
import type ReactECharts from 'echarts-for-react'

import { type KlineChartData } from './stockChartView/klineData'
import {
  computePriceAxisRange,
  DEFAULT_ZOOM_END,
  DEFAULT_ZOOM_START,
} from './stockChartView/klineOption'

interface DataZoomRange {
  start?: number
  end?: number
  startValue?: number | string
  endValue?: number | string
}

export function useDataZoomYAxisRescale(
  chartRef: RefObject<ReactECharts | null>,
  chartData: KlineChartData | null | undefined,
) {
  /** 复位缩放到默认窗口（双击图表 / 工具栏按钮） */
  const resetZoom = () => {
    chartRef.current
      ?.getEchartsInstance()
      .dispatchAction({ type: 'dataZoom', start: DEFAULT_ZOOM_START, end: DEFAULT_ZOOM_END })
  }

  /** 缩放后按可见窗口重算主图纵轴（右轴价格 / 左轴涨跌幅） */
  const handleDataZoom = () => {
    const chart = chartRef.current?.getEchartsInstance()
    if (!chart || !chartData || chartData.bars.length === 0) return
    const dz = (chart.getOption().dataZoom as DataZoomRange[] | undefined)?.[0]
    if (!dz) return
    const len = chartData.bars.length
    const toIndex = (
      value: number | string | undefined,
      ratio: number | undefined,
      fallback: number,
    ): number => {
      if (typeof value === 'number') return value
      if (typeof value === 'string') {
        const idx = chartData.dates.indexOf(value)
        if (idx >= 0) return idx
      }
      if (typeof ratio === 'number') return Math.round(((len - 1) * ratio) / 100)
      return fallback
    }
    const startIdx = Math.max(0, toIndex(dz.startValue, dz.start, 0))
    const endIdx = Math.min(
      len - 1,
      Math.max(startIdx, toIndex(dz.endValue, dz.end, len - 1)),
    )
    const { yMin, yMax, pctMin, pctMax } = computePriceAxisRange(
      chartData.bars,
      startIdx,
      endIdx,
    )
    chart.setOption({
      yAxis: [
        { min: yMin, max: yMax },
        { min: pctMin, max: pctMax },
      ],
    })
  }

  return { resetZoom, handleDataZoom }
}
