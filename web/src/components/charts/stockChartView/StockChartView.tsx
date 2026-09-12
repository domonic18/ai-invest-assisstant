import { SyncOutlined } from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { Button, Spin } from 'antd'
import { useMemo, useState } from 'react'

import { IntradayChart } from '@/components/charts/IntradayChart'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useStockIntraday, useStockKline } from '@/hooks/useStocks'
import { useMaConfigs } from '@/stores/settings'
import type { IndexIntraday } from '@ai-invest/shared'

import { BORDER_COLOR, PANEL_BG } from './constants'
import { ChartToolbar } from './ChartToolbar'
import { KlineEmptyState } from './KlineEmptyState'
import { buildKlineOption, computePriceAxisRange, prepareKlineData } from './klineOption'
import { useAutoCollectKline } from './useAutoCollectKline'
import { useChartFullscreen } from './useChartFullscreen'

export interface StockChartViewIndicators {
  volume: boolean
  ma: boolean
  macd: boolean
  kdj: boolean
}

export interface StockChartViewProps {
  code: string
  defaultPeriod?: string
  defaultIndicators?: Partial<StockChartViewIndicators>
  onPeriodChange?: (period: string) => void
  onIndicatorsChange?: (indicators: StockChartViewIndicators) => void
  height?: number
  /** 单图/双图切换（原型仅首图工具栏展示） */
  layoutToggle?: { value: boolean; onChange: (dual: boolean) => void }
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
  defaultPeriod = 'daily',
  defaultIndicators = {},
  onPeriodChange,
  onIndicatorsChange,
  height = 460,
  layoutToggle,
}: StockChartViewProps) {
  const [period, setPeriod] = useState(defaultPeriod)
  const [indicators, setIndicators] = useState<StockChartViewIndicators>({
    volume: true,
    ma: true,
    macd: false,
    kdj: false,
    ...defaultIndicators,
  })

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

  const chartData = useMemo(() => {
    if (isIntraday || !klineData || klineData.bars.length === 0) return null
    return prepareKlineData(klineData, maConfigs)
  }, [klineData, isIntraday, maConfigs])

  const option = useMemo(() => {
    if (!chartData) return undefined
    return buildKlineOption(chartData, indicators, effectiveHeight)
  }, [chartData, indicators, effectiveHeight])

  const { chartRef, wrapperProps, onEvents: navEvents } = useKlineKeyboardNav(
    chartData?.dates.length ?? 0,
  )

  // 复位缩放到默认窗口（双击图表 / 设置弹层按钮）
  const resetZoom = () => {
    chartRef.current
      ?.getEchartsInstance()
      .dispatchAction({ type: 'dataZoom', start: 50, end: 100 })
  }

  // 缩放（键盘 ↑/↓、滚轮、滑块）后按可见窗口重算主图纵轴，对齐同花顺行为
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

  const isLoading = isIntraday ? intradayLoading : klineLoading
  const hasData = isIntraday
    ? intradayData != null && intradayData.points.length > 0
    : chartData != null && chartData.bars.length > 0

  // K 线缺数据/落后最近交易日时自动补采（仅日 K 视图做落后判定，周/月聚合桶日期不可比）
  const dailyView = !isIntraday && period === 'daily'
  const latestTradeDateForDisplay = dailyView ? (klineData?.latestTradeDate ?? '') : ''
  const { collect: collectKline, behind: klineBehind, suppressed: publishPending } = useAutoCollectKline(
    code,
    {
      ready: !isIntraday && !klineLoading,
      missing: !isIntraday && !klineLoading && !hasData,
      lastBarDate: dailyView ? klineData?.bars[klineData.bars.length - 1]?.date : undefined,
      latestTradeDate: dailyView ? klineData?.latestTradeDate : undefined,
    },
  )

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
              onClick={() => collectKline.mutate(latestTradeDateForDisplay)}
            >
              立即补采
            </Button>
          )}
        </div>
      )}

      {/* Chart area */}
      <div className="relative flex-1 min-h-0">
        {/* MA 常驻数值行（悬浮于主图左上） */}
        {indicators.ma && !isIntraday && chartData && (
          <div className="absolute top-1.5 left-[52px] z-10 flex gap-3 font-mono text-[11px] pointer-events-none">
            {chartData.mas.map((ma) => {
              const latest = ma.values[ma.values.length - 1]
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
            <IntradayChart data={adaptToIndexIntraday(intradayData)} height={effectiveHeight} />
          )
        ) : option ? (
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
        ) : null}
      </div>
    </div>
  )
}
