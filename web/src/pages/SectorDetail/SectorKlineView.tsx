import ReactECharts from 'echarts-for-react'
import { useMemo, useState } from 'react'

import { ChartToolbar } from '@/components/charts/stockChartView/ChartToolbar'
import { BORDER_COLOR, PANEL_BG } from '@/components/charts/stockChartView/constants'
import {
  buildKlineOption,
  computePriceAxisRange,
  prepareKlineData,
} from '@/components/charts/stockChartView/klineOption'
import type { StockChartViewIndicators } from '@/components/charts/stockChartView/StockChartView'
import { useChartFullscreen } from '@/components/charts/stockChartView/useChartFullscreen'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useMaConfigs } from '@/stores/settings'
import type { StockKlineBar } from '@ai-invest/shared'
import { aggregateWeeklyBars, weekStartDate } from '@/utils/kline'

import { DEFAULT_SECTOR_INDICATORS, SECTOR_PERIOD_OPTIONS } from './sectorChartConfig'

interface SectorKlineViewProps {
  bars: StockKlineBar[]
  /** 异动日竖线标注（周 K 视图自动映射到所在周的最后交易日）。 */
  markers?: { date: string; label?: string }[]
  height: number
  defaultPeriod?: 'daily' | 'weekly'
  defaultIndicators?: Partial<StockChartViewIndicators>
  /** 单图/双图切换（仅首图工具栏展示）。 */
  layoutToggle?: { value: boolean; onChange: (dual: boolean) => void }
}

export function SectorKlineView({
  bars,
  markers,
  height,
  defaultPeriod = 'daily',
  defaultIndicators = {},
  layoutToggle,
}: SectorKlineViewProps) {
  const [period, setPeriod] = useState<'daily' | 'weekly'>(defaultPeriod)
  const [indicators, setIndicators] = useState<StockChartViewIndicators>({
    ...DEFAULT_SECTOR_INDICATORS,
    ...defaultIndicators,
  })
  const maConfigs = useMaConfigs()

  const { rootRef, isFullscreen, fsHeight, toggleFullscreen } = useChartFullscreen()
  const effectiveHeight = fsHeight ?? height

  const barsForPeriod = useMemo(
    () => (period === 'weekly' ? aggregateWeeklyBars(bars) : bars),
    [bars, period],
  )

  const chartData = useMemo(
    () =>
      barsForPeriod.length > 0
        ? prepareKlineData({ bars: barsForPeriod }, maConfigs)
        : undefined,
    [barsForPeriod, maConfigs],
  )

  const markersForPeriod = useMemo(() => {
    if (!markers || markers.length === 0 || period === 'daily') return markers
    return markers
      .map((m) => {
        const hit = barsForPeriod.find(
          (b) => weekStartDate(b.date) === weekStartDate(m.date),
        )
        return hit ? { ...m, date: hit.date } : null
      })
      .filter((m): m is { date: string; label?: string } => m != null)
  }, [markers, period, barsForPeriod])

  const option = useMemo(
    () =>
      chartData
        ? buildKlineOption(chartData, indicators, effectiveHeight, markersForPeriod)
        : undefined,
    [chartData, indicators, effectiveHeight, markersForPeriod],
  )

  const { chartRef, wrapperProps, onEvents: navEvents } = useKlineKeyboardNav(
    chartData?.dates.length ?? 0,
  )

  const resetZoom = () => {
    chartRef.current
      ?.getEchartsInstance()
      .dispatchAction({ type: 'dataZoom', start: 50, end: 100 })
  }

  // 缩放后按可见窗口重算主图纵轴，对齐个股图表行为
  const handleDataZoom = () => {
    const chart = chartRef.current?.getEchartsInstance()
    if (!chart || !chartData || chartData.bars.length === 0) return
    const dz = (
      chart.getOption().dataZoom as
        | { start?: number; end?: number; startValue?: number | string; endValue?: number | string }[]
        | undefined
    )?.[0]
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

  const onEvents = {
    ...navEvents,
    dblclick: resetZoom,
    datazoom: handleDataZoom,
  }

  return (
    <div
      ref={rootRef}
      className="flex flex-col"
      style={{ backgroundColor: PANEL_BG, border: `1px solid ${BORDER_COLOR}` }}
    >
      <ChartToolbar
        period={period}
        onPeriodChange={(p) => setPeriod(p as 'daily' | 'weekly')}
        indicators={indicators}
        onToggleIndicator={(key) =>
          setIndicators((prev) => ({ ...prev, [key]: !prev[key] }))
        }
        periodOptions={SECTOR_PERIOD_OPTIONS}
        layoutToggle={layoutToggle}
        onResetZoom={resetZoom}
        isFullscreen={isFullscreen}
        onToggleFullscreen={toggleFullscreen}
      />
      {option ? (
        <div {...wrapperProps}>
          <ReactECharts
            ref={chartRef}
            option={option}
            style={{ height: `${effectiveHeight}px`, width: '100%' }}
            onEvents={onEvents}
            opts={{ renderer: 'canvas' }}
            notMerge
          />
        </div>
      ) : (
        <div
          className="flex items-center justify-center text-xs text-[#8c8c8c]"
          style={{ height: effectiveHeight }}
        >
          暂无 K 线数据
        </div>
      )}
    </div>
  )
}
