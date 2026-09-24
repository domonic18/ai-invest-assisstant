import ReactECharts from 'echarts-for-react'
import { useMemo, useState } from 'react'
import type { ECharts } from 'echarts'

import { DrawingLayerHost } from '@/components/charts/drawing/DrawingLayerHost'
import { ChartToolbar } from '@/components/charts/stockChartView/ChartToolbar'
import { BORDER_COLOR, PANEL_BG } from '@/components/charts/stockChartView/constants'
import { prepareKlineData } from '@/components/charts/stockChartView/klineData'
import { buildKlineOption } from '@/components/charts/stockChartView/klineOption'
import type { StockChartViewIndicators } from '@/components/charts/stockChartView/StockChartView'
import { useChartFullscreen } from '@/components/charts/stockChartView/useChartFullscreen'
import { useDataZoomYAxisRescale } from '@/components/charts/useDataZoomYAxisRescale'
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
  /** 画线归属（板块代码）；不传则不启用画线图层。 */
  drawingCode?: string
}

export function SectorKlineView({
  bars,
  markers,
  height,
  defaultPeriod = 'daily',
  defaultIndicators = {},
  layoutToggle,
  drawingCode,
}: SectorKlineViewProps) {
  const [period, setPeriod] = useState<'daily' | 'weekly'>(defaultPeriod)
  const [indicators, setIndicators] = useState<StockChartViewIndicators>({
    ...DEFAULT_SECTOR_INDICATORS,
    ...defaultIndicators,
  })
  const maConfigs = useMaConfigs()

  // 画线图层实例（onChartReady 捕获）；未传 drawingCode 时不启用
  const [drawingChart, setDrawingChart] = useState<ECharts | null>(null)

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

  const { resetZoom, handleDataZoom } = useDataZoomYAxisRescale(chartRef, chartData)

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
        drawing={!!drawingCode}
        layoutToggle={layoutToggle}
        onResetZoom={resetZoom}
        isFullscreen={isFullscreen}
        onToggleFullscreen={toggleFullscreen}
      />
      {option ? (
        <div {...wrapperProps} className="relative">
          <ReactECharts
            ref={chartRef}
            option={option}
            style={{ height: `${effectiveHeight}px`, width: '100%' }}
            onEvents={onEvents}
            opts={{ renderer: 'canvas' }}
            notMerge
            onChartReady={setDrawingChart}
          />
          {drawingCode && (
            <DrawingLayerHost
              chart={drawingChart}
              dates={chartData?.dates ?? []}
              target={{ targetType: 'sector', targetCode: drawingCode }}
              period={period}
            />
          )}
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
