import { CloseOutlined, SyncOutlined } from '@ant-design/icons'
import { Button, Spin, Typography } from 'antd'
import ReactECharts from 'echarts-for-react'
import { useMemo, useState } from 'react'

import { IntradayChart } from '@/components/charts/IntradayChart'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useCollectStockKline } from '@/hooks/useCollectStockKline'
import { useStockIntraday, useStockKline } from '@/hooks/useStocks'
import { useColorScheme } from '@/stores/settings'
import type { IndexIntraday } from '@ai-invest/shared'

import { IndicatorButton } from './IndicatorButton'
import {
  BarChartOutlined,
  FundOutlined,
  LineChartOutlined,
} from '@ant-design/icons'
import {
  BORDER_COLOR,
  PANEL_BG,
  PERIOD_OPTIONS,
} from './constants'
import { buildKlineOption, prepareKlineData } from './klineOption'

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
  onRemove?: () => void
  onPeriodChange?: (period: string) => void
  onIndicatorsChange?: (indicators: StockChartViewIndicators) => void
  height?: number
  title?: string
}

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
  onRemove,
  onPeriodChange,
  onIndicatorsChange,
  height = 460,
  title,
}: StockChartViewProps) {
  useColorScheme()
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
  const collectKline = useCollectStockKline(code)

  const isIntraday = period === 'intraday'

  const chartData = useMemo(() => {
    if (isIntraday || !klineData || klineData.bars.length === 0) return null
    return prepareKlineData(klineData)
  }, [klineData, isIntraday])

  const option = useMemo(() => {
    if (!chartData) return undefined
    return buildKlineOption(chartData, indicators, height)
  }, [chartData, indicators, height])

  const { chartRef, wrapperProps, onEvents } = useKlineKeyboardNav(
    chartData?.dates.length ?? 0,
  )

  const isLoading = isIntraday ? intradayLoading : klineLoading
  const hasData = isIntraday
    ? intradayData != null && intradayData.points.length > 0
    : chartData != null && chartData.bars.length > 0

  return (
    <div
      className="flex flex-col"
      style={{ backgroundColor: PANEL_BG, border: `1px solid ${BORDER_COLOR}` }}
    >
      {/* Top toolbar: period tabs + title + remove */}
      <div
        className="flex items-center justify-between px-2 py-1.5"
        style={{ borderBottom: `1px solid ${BORDER_COLOR}` }}
      >
        <div className="flex items-center gap-3">
          {title && (
            <span className="text-xs font-medium text-[#d1d4dc]">{title}</span>
          )}
          <div className="flex items-center">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => handlePeriodChange(opt.value)}
                className={`px-3 py-0.5 text-xs transition-colors ${
                  period === opt.value
                    ? 'text-[#d1d4dc] bg-[#2a2e38] rounded'
                    : 'text-[#8c8c8c] hover:text-[#d1d4dc]'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        {onRemove && (
          <Button
            type="text"
            size="small"
            icon={<CloseOutlined />}
            onClick={onRemove}
            className="text-[#8c8c8c] hover:text-[#ff4d4f]"
          />
        )}
      </div>

      {/* Chart area */}
      <div className="relative flex-1 min-h-0">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center gap-2 text-[#8c8c8c]" style={{ height }}>
            <Spin size="small" />
            <span className="text-xs">正在拉取{isIntraday ? '分时' : 'K 线'}数据...</span>
          </div>
        ) : !hasData ? (
          <div
            className="flex flex-col items-center justify-center gap-3 text-[#8c8c8c]"
            style={{ height }}
          >
            <Typography.Text type="secondary" className="text-sm">
              {isIntraday ? '暂无分时数据' : '暂无 K 线数据'}
            </Typography.Text>
            {!isIntraday && (
              <>
                <Button
                  size="small"
                  icon={<SyncOutlined spin={collectKline.isPending} />}
                  loading={collectKline.isPending}
                  onClick={() => collectKline.mutate()}
                >
                  {collectKline.isPending ? '采集中，预计 10-30 秒...' : '补采 K 线数据'}
                </Button>
                {collectKline.isError && (
                  <Typography.Text type="danger" className="text-xs">
                    {(collectKline.error as Error).message}
                  </Typography.Text>
                )}
                {collectKline.isSuccess && (
                  <Typography.Text type="success" className="text-xs">
                    采集完成
                  </Typography.Text>
                )}
              </>
            )}
          </div>
        ) : isIntraday ? (
          intradayData && (
            <IntradayChart data={adaptToIndexIntraday(intradayData)} height={height} />
          )
        ) : option ? (
          <div {...wrapperProps}>
            <ReactECharts
              ref={chartRef}
              option={option}
              style={{ height: `${height}px`, width: '100%' }}
              onEvents={onEvents}
              opts={{ renderer: 'canvas' }}
              notMerge
            />
          </div>
        ) : null}
      </div>

      {/* Bottom toolbar: indicator toggles */}
      <div
        className="flex items-center gap-1 px-2 py-1.5"
        style={{ borderTop: `1px solid ${BORDER_COLOR}` }}
      >
        <IndicatorButton
          active={indicators.volume}
          label="成交量"
          icon={<BarChartOutlined />}
          onClick={() => toggleIndicator('volume')}
        />
        <IndicatorButton
          active={indicators.ma}
          label="MA"
          icon={<LineChartOutlined />}
          onClick={() => toggleIndicator('ma')}
        />
        <IndicatorButton
          active={indicators.macd}
          label="MACD"
          icon={<FundOutlined />}
          onClick={() => toggleIndicator('macd')}
        />
        <IndicatorButton
          active={indicators.kdj}
          label="KDJ"
          icon={<LineChartOutlined />}
          onClick={() => toggleIndicator('kdj')}
        />
      </div>
    </div>
  )
}
