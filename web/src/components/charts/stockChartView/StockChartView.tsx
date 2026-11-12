import { SyncOutlined } from '@ant-design/icons'
import ReactECharts from '@/components/charts/ReactECharts'
import { Button, Spin } from 'antd'
import { useEffect, useLayoutEffect, useMemo, useState } from 'react'

import { IntradayChart } from '@/components/charts/IntradayChart'
import { DrawingLayerHost } from '@/components/charts/drawing/DrawingLayerHost'
import { useDrawingStore } from '@/stores/drawing'
import { resolveZoomWindow, useKlineViewLayoutStore } from '@/stores/klineViewLayout'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useStockIntraday, useStockKline } from '@/hooks/useStocks'
import { useMaConfigs } from '@/stores/settings'
import type { ECharts } from 'echarts'
import type { ApiPaperTradeTradeMarker, IndexIntraday, KlineDrawingPeriod } from '@ai-invest/shared'

import { BORDER_COLOR, PANEL_BG } from './constants'
import { ChartToolbar } from './ChartToolbar'
import { KlineEmptyState } from './KlineEmptyState'
import { prepareKlineData } from './klineData'
import { buildKlineOption } from './klineOption'
import { applySubPaneLegends } from './klinePanes'
import type { SubPaneKey } from './klinePanes'
import {
  toIntradayTradeMarks,
  toKlineTradeMarks,
} from './tradeMarkers'
import { useAutoCollectKline } from './useAutoCollectKline'
import { useChartFullscreen } from './useChartFullscreen'
import { useDataZoomYAxisRescale } from '@/components/charts/useDataZoomYAxisRescale'

export interface StockChartViewIndicators {
  volume: boolean
  ma: boolean
  macd: boolean
  kdj: boolean
}

export interface StockChartViewProps {
  code: string
  /** 视图槽位标识（daily/weekly）：跨股票继承周期与缩放窗口的会话 store key */
  viewId: string
  defaultPeriod?: string
  defaultIndicators?: Partial<StockChartViewIndicators>
  onPeriodChange?: (period: string) => void
  onIndicatorsChange?: (indicators: StockChartViewIndicators) => void
  height?: number
  /** 单图/双图切换（原型仅首图工具栏展示） */
  layoutToggle?: { value: boolean; onChange: (dual: boolean) => void }
  /** 模拟盘成交回报（当前用户全账户、按 code 过滤），渲染 B/S/T 标记。 */
  tradeMarks?: ApiPaperTradeTradeMarker[]
}

/** 工具栏 36 + 底边框 1；MA 数值行悬浮于主图内，不占布局高度。 */
export const CHROME_HEIGHT = 37

function adaptToIndexIntraday(stockIntraday: {
  code: string
  name: string
  tradeDate: string
  prevClose: number
  points: { time: string; price: number; volume: number; amount: number }[]
}): IndexIntraday {
  return stockIntraday as IndexIntraday
}

export function StockChartView({
  code,
  viewId,
  defaultPeriod = 'daily',
  defaultIndicators = {},
  onPeriodChange,
  onIndicatorsChange,
  height = 460,
  layoutToggle,
  tradeMarks,
}: StockChartViewProps) {
  const [period, setPeriod] = useState(defaultPeriod)
  const [indicators, setIndicators] = useState<StockChartViewIndicators>({
    volume: true,
    ma: true,
    macd: false,
    kdj: false,
    ...defaultIndicators,
  })

  // 周期跟随 prop（父级会话 store 跨股票继承的值），组件复用不重挂时同步内部状态
  useEffect(() => {
    setPeriod(defaultPeriod)
  }, [defaultPeriod])

  const handlePeriodChange = (value: string) => {
    setPeriod(value)
    onPeriodChange?.(value)
  }

  const toggleIndicator = (key: keyof StockChartViewIndicators) => {
    setIndicators((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      onIndicatorsChange?.(next)
      return next
    })
  }

  const klineParams =
    period === 'daily' || period === 'weekly' || period === 'monthly'
      ? { period: period as 'daily' | 'weekly' | 'monthly', limit: 250 }
      : { period: 'daily' as const, limit: 250 }

  const { data: klineData, isLoading: klineLoading } = useStockKline(code, klineParams)
  const { data: intradayData, isLoading: intradayLoading } = useStockIntraday(code)
  const maConfigs = useMaConfigs()

  const isIntraday = period === 'intraday'

  const { rootRef, isFullscreen, fsHeight, toggleFullscreen } = useChartFullscreen()
  const effectiveHeight = fsHeight ?? height

  // 画线图层（分钟线不提供画线）；实例经 onChartReady 捕获
  const [drawingChart, setDrawingChart] = useState<ECharts | null>(null)
  const drawingPeriod: KlineDrawingPeriod =
    period === 'daily' || period === 'weekly' || period === 'monthly' ? period : 'daily'
  const drawingEnabled = !isIntraday && !!code
  // 分时等画线不可用周期：Host 卸载，编辑态残留会导致按钮高亮但 Esc 失效，先退出编辑态
  useEffect(() => {
    if (!drawingEnabled) useDrawingStore.getState().exitDrawing()
  }, [drawingEnabled])

  const chartData = useMemo(() => {
    if (isIntraday || !klineData || klineData.bars.length === 0) return null
    return prepareKlineData(klineData, maConfigs)
  }, [klineData, isIntraday, maConfigs])

  const klineTradeMarks = useMemo(
    () => toKlineTradeMarks(tradeMarks ?? []),
    [tradeMarks],
  )
  const intradayTradeMarks = useMemo(
    () => toIntradayTradeMarks(tradeMarks ?? []),
    [tradeMarks],
  )

  const option = useMemo(() => {
    if (!chartData) return undefined
    return buildKlineOption(chartData, indicators, effectiveHeight, undefined, klineTradeMarks)
  }, [chartData, indicators, effectiveHeight, klineTradeMarks])

  const { chartRef, wrapperProps, onEvents: navEvents } = useKlineKeyboardNav(
    chartData?.dates.length ?? 0,
  )

  // 图例值锚定可见窗口尾 bar：初始 null=序列尾，缩放/平移后由 datazoom 回调更新
  const [visibleEndIdx, setVisibleEndIdx] = useState<number | null>(null)
  useEffect(() => {
    setVisibleEndIdx(null)
  }, [chartData])

  const { resetZoom, handleDataZoom } = useDataZoomYAxisRescale(chartRef, chartData, {
    onWindowChange: (startIdx, endIdx) => {
      setVisibleEndIdx((prev) => (prev === endIdx ? prev : endIdx))
      // 缩放窗口写入会话 store（span + 距最新 bar 偏移），切股后按新数据长度恢复
      const len = chartData?.bars.length ?? 0
      if (len > 0 && endIdx >= startIdx && startIdx >= 0) {
        useKlineViewLayoutStore.getState().setWindow(viewId, {
          span: endIdx - startIdx + 1,
          endOffset: Math.max(0, len - 1 - endIdx),
        })
      }
    },
  })

  // 跨股票/周期切换继承缩放窗口：新数据渲染后按记忆的 span/endOffset（锚定最新 bar）
  // 恢复；store 无记录（本会话未调整过）则保持默认窗口。layout 阶段派发避免默认窗口闪帧
  useLayoutEffect(() => {
    if (isIntraday || !chartData || chartData.bars.length === 0) return
    const saved = useKlineViewLayoutStore.getState().windows[viewId]
    if (!saved) return
    const chart = chartRef.current?.getEchartsInstance()
    if (!chart) return
    const { start, end } = resolveZoomWindow(saved, chartData.bars.length)
    chart.dispatchAction({ type: 'dataZoom', startValue: start, endValue: end })
  }, [chartData, viewId, isIntraday, chartRef])

  const enabledSubKeys = useMemo(
    () =>
      (['volume', 'macd', 'kdj'] as const).filter(
        (key) => indicators[key],
      ) as SubPaneKey[],
    [indicators],
  )
  const legendIdx = visibleEndIdx ?? Math.max((chartData?.bars.length ?? 1) - 1, 0)

  // 缩放到历史区间 / option 重建后，副图图例按窗口尾 bar 取值（title 按 id merge）
  useEffect(() => {
    if (isIntraday || !chartData || !enabledSubKeys.length) return
    const chart = chartRef.current?.getEchartsInstance()
    if (!chart) return
    applySubPaneLegends(chart, chartData, enabledSubKeys, legendIdx)
  }, [chartData, chartRef, enabledSubKeys, legendIdx, isIntraday, option])

  const onEvents = {
    ...navEvents,
    dblclick: resetZoom,
    datazoom: handleDataZoom,
  }

  const isLoading = isIntraday ? intradayLoading : klineLoading
  const hasData = isIntraday
    ? intradayData != null && intradayData.points.length > 0
    : chartData != null && chartData.bars.length > 0

  // K 线缺数据/历史过浅/落后最近交易日时自动补采（仅日 K 视图做落后与历史深度判定，周/月聚合桶日期不可比）
  const dailyView = !isIntraday && period === 'daily'
  const latestTradeDateForDisplay = dailyView ? (klineData?.latestTradeDate ?? '') : ''
  const minHealthyBars = dailyView ? (klineData?.minHealthyBars ?? 60) : 60
  const {
    collect: collectKline,
    behind: klineBehind,
    suppressed: publishPending,
    truncated: klineTruncated,
  } = useAutoCollectKline(code, {
    ready: !isIntraday && !klineLoading,
    missing: !isIntraday && !klineLoading && !hasData,
    lastBarDate: dailyView ? klineData?.bars[klineData.bars.length - 1]?.date : undefined,
    latestTradeDate: dailyView ? klineData?.latestTradeDate : undefined,
    insufficient: dailyView ? klineData?.needsBackfill : undefined,
    minHealthyBars: dailyView ? klineData?.minHealthyBars : undefined,
    firstBarDate: dailyView ? klineData?.bars[0]?.date : undefined,
  })

  return (
    <div
      ref={rootRef}
      className="flex flex-col"
      style={{ backgroundColor: PANEL_BG, border: `1px solid ${BORDER_COLOR}` }}
    >
      <ChartToolbar
        period={period}
        onPeriodChange={handlePeriodChange}
        indicators={indicators}
        onToggleIndicator={toggleIndicator}
        layoutToggle={layoutToggle}
        drawing={drawingEnabled}
        onResetZoom={resetZoom}
        isFullscreen={isFullscreen}
        onToggleFullscreen={toggleFullscreen}
      />

      {klineBehind && !publishPending && (
        <div
          className="flex items-center justify-between gap-2 border-b px-3 py-1.5 text-xs"
          style={{ borderColor: BORDER_COLOR }}
        >
          <span className={collectKline.isError ? 'text-red-400' : 'text-[#8c8c8c]'}>
            {collectKline.isError
              ? (collectKline.error as Error).message
              : `K 线未更新至最近交易日（${latestTradeDateForDisplay}），${
                  collectKline.isPending ? '正在自动补采，预计 10-30 秒...' : '数据可能滞后'
                }`}
          </span>

          {!collectKline.isPending && (
            <Button
              type="link"
              size="small"
              icon={<SyncOutlined />}
              onClick={() =>
                collectKline.mutate({ mode: 'freshness', notBefore: latestTradeDateForDisplay })
              }
            >
              立即补采
            </Button>
          )}
        </div>
      )}

      {klineTruncated && (
        <div
          className="flex items-center justify-between gap-2 border-b px-3 py-1.5 text-xs"
          style={{ borderColor: BORDER_COLOR }}
        >
          <span className={collectKline.isError ? 'text-red-400' : 'text-[#8c8c8c]'}>
            {collectKline.isError
              ? (collectKline.error as Error).message
              : `历史数据不足（当前 ${klineData?.bars.length ?? 0} 根，目标 ${minHealthyBars} 根），${
                  collectKline.isPending ? '正在自动补采全历史...' : '历史可能被截断'
                }`}
          </span>

          {!collectKline.isPending && (
            <Button
              type="link"
              size="small"
              icon={<SyncOutlined />}
              onClick={() =>
                collectKline.mutate({
                  mode: 'depth',
                  minBars: minHealthyBars,
                  beforeFirstBarDate: klineData?.bars[0]?.date,
                })
              }
            >
              立即补采
            </Button>
          )}
        </div>
      )}

      {/* Chart area */}
      <div className="relative flex-1 min-h-0">
        {/* MA 常驻数值行（悬浮于主图左上，宽度避开右侧 60px 价格轴标签区） */}
        {indicators.ma && !isIntraday && chartData && (
          <div className="absolute top-1.5 left-[52px] right-[68px] z-10 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[11px] pointer-events-none">
            {chartData.mas.map((ma) => {
              const latest = ma.values[legendIdx]
              return (
                <span key={ma.period} style={{ color: ma.color }}>
                  MA{ma.period}: {latest == null ? '--' : latest.toFixed(2)}
                </span>
              )
            })}
          </div>
        )}
        {isLoading ? (
          <div className="flex flex-col items-center justify-center gap-2 text-[#8c8c8c]" style={{ height: effectiveHeight }}>
            <Spin size="small" />
            <span className="text-xs">正在拉取{isIntraday ? '分时' : 'K 线'}数据...</span>
          </div>
        ) : !hasData ? (
          <KlineEmptyState isIntraday={isIntraday} height={effectiveHeight} collectKline={collectKline} />
        ) : isIntraday ? (
          intradayData && (
            <IntradayChart
              data={adaptToIndexIntraday(intradayData)}
              height={effectiveHeight}
              markers={intradayTradeMarks}
            />
          )
        ) : option ? (
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
            {drawingEnabled && (
              <DrawingLayerHost
                chart={drawingChart}
                dates={chartData?.dates ?? []}
                target={{ targetType: 'stock', targetCode: code }}
                period={drawingPeriod}
              />
            )}
          </div>
        ) : null}
      </div>
    </div>
  )
}
