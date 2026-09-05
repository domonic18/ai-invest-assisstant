import {
  CheckOutlined,
  DownOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  SettingOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { Button, Dropdown, Popover, Radio, Spin, Typography } from 'antd'
import ReactECharts from 'echarts-for-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { IntradayChart } from '@/components/charts/IntradayChart'
import { useKlineKeyboardNav } from '@/components/charts/useKlineKeyboardNav'
import { useCollectStockKline } from '@/hooks/useCollectStockKline'
import { useStockIntraday, useStockKline } from '@/hooks/useStocks'
import { useSettingsStore } from '@/stores/settings'
import type { IndexIntraday } from '@ai-invest/shared'

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
  onPeriodChange?: (period: string) => void
  onIndicatorsChange?: (indicators: StockChartViewIndicators) => void
  height?: number
  /** 单图/双图切换（原型仅首图工具栏展示） */
  layoutToggle?: { value: boolean; onChange: (dual: boolean) => void }
}

const INDICATOR_OPTIONS: { key: keyof StockChartViewIndicators; label: string }[] = [
  { key: 'volume', label: 'VOL' },
  { key: 'ma', label: 'MA' },
  { key: 'macd', label: 'MACD' },
  { key: 'kdj', label: 'KDJ' },
]

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
  const colorScheme = useSettingsStore((s) => s.colorScheme)
  const setColorScheme = useSettingsStore((s) => s.setColorScheme)
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

  // 全屏：根元素 requestFullscreen，画布高度跟随窗口
  const rootRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [fsHeight, setFsHeight] = useState<number | null>(null)
  useEffect(() => {
    const onFsChange = () => {
      const active = document.fullscreenElement === rootRef.current
      setIsFullscreen(active)
      setFsHeight(active ? window.innerHeight - CHROME_HEIGHT - 2 : null)
    }
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])
  const toggleFullscreen = () => {
    if (document.fullscreenElement != null) {
      void document.exitFullscreen()
    } else {
      void rootRef.current?.requestFullscreen()
    }
  }
  const effectiveHeight = fsHeight ?? height

  const chartData = useMemo(() => {
    if (isIntraday || !klineData || klineData.bars.length === 0) return null
    return prepareKlineData(klineData)
  }, [klineData, isIntraday])

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
  const onEvents = {
    ...navEvents,
    dblclick: resetZoom,
  }

  const isLoading = isIntraday ? intradayLoading : klineLoading
  const hasData = isIntraday
    ? intradayData != null && intradayData.points.length > 0
    : chartData != null && chartData.bars.length > 0

  const indicatorItems = INDICATOR_OPTIONS.map((opt) => ({
    key: opt.key,
    label: (
      <span className="flex items-center justify-between gap-4">
        {opt.label}
        {indicators[opt.key] && <CheckOutlined className="text-[10px]" />}
      </span>
    ),
  }))

  const activeIndicatorLabels = INDICATOR_OPTIONS.filter(
    (opt) => indicators[opt.key],
  ).map((opt) => opt.label)

  return (
    <div
      ref={rootRef}
      className="flex flex-col"
      style={{ backgroundColor: PANEL_BG, border: `1px solid ${BORDER_COLOR}` }}
    >
      {/* Toolbar: period seg + indicator dropdown + layout/settings/fullscreen */}
      <div
        className="flex items-center gap-2 px-2.5 shrink-0"
        style={{ height: 36, borderBottom: `1px solid ${BORDER_COLOR}` }}
      >
        <div className="flex items-center gap-0.5 rounded-md p-0.5 bg-[#1c1f26]">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => handlePeriodChange(opt.value)}
              className={`px-2.5 py-[3px] text-xs rounded transition-colors ${
                period === opt.value
                  ? 'font-medium bg-[rgba(94,106,210,0.12)] text-[#5e6ad2]'
                  : 'text-[#8a8f98] hover:text-[#f0f1f5]'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <span className="w-px h-4 bg-[#23262d]" />
        <Dropdown
          trigger={['click']}
          menu={{
            items: indicatorItems,
            onClick: ({ key }) => toggleIndicator(key as keyof StockChartViewIndicators),
          }}
        >
          <button
            type="button"
            className="flex items-center gap-1 px-2 py-[3px] text-xs text-[#8a8f98] border border-[#23262d] rounded transition-colors hover:text-[#f0f1f5] hover:border-[#2e323c]"
          >
            {activeIndicatorLabels.length > 0
              ? `指标：${activeIndicatorLabels.join(' · ')}`
              : '指标'}
            <DownOutlined className="!text-[9px]" />
          </button>
        </Dropdown>

        <div className="ml-auto flex items-center gap-1.5">
          {layoutToggle && (
            <div className="flex items-center gap-0.5 rounded-md p-0.5 bg-[#1c1f26]">
              {([true, false] as const).map((v) => (
                <button
                  key={v ? 'dual' : 'single'}
                  type="button"
                  onClick={() => layoutToggle.onChange(v)}
                  className={`px-2 py-[3px] text-xs rounded transition-colors ${
                    layoutToggle.value === v
                      ? 'font-medium bg-[rgba(94,106,210,0.12)] text-[#5e6ad2]'
                      : 'text-[#8a8f98] hover:text-[#f0f1f5]'
                  }`}
                >
                  {v ? '双图' : '单图'}
                </button>
              ))}
            </div>
          )}
          <Popover
            trigger="click"
            placement="bottomRight"
            content={
              <div className="w-44 space-y-2.5">
                <div>
                  <div className="text-xs text-[#8a8f98] mb-1.5">涨跌配色</div>
                  <Radio.Group
                    size="small"
                    value={colorScheme}
                    onChange={(e) => setColorScheme(e.target.value)}
                  >
                    <Radio.Button value="cn">红涨绿跌</Radio.Button>
                    <Radio.Button value="us">绿涨红跌</Radio.Button>
                  </Radio.Group>
                </div>
                <Button size="small" block onClick={resetZoom}>
                  复位缩放窗口
                </Button>
              </div>
            }
          >
            <button
              type="button"
              title="图表设置"
              className="flex items-center justify-center w-[26px] h-[26px] rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
            >
              <SettingOutlined className="!text-[13px]" />
            </button>
          </Popover>
          <button
            type="button"
            title={isFullscreen ? '退出全屏' : '全屏'}
            onClick={toggleFullscreen}
            className="flex items-center justify-center w-[26px] h-[26px] rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
          >
            {isFullscreen ? (
              <FullscreenExitOutlined className="!text-[13px]" />
            ) : (
              <FullscreenOutlined className="!text-[13px]" />
            )}
          </button>
        </div>
      </div>

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
          <div
            className="flex flex-col items-center justify-center gap-3 text-[#8c8c8c]"
            style={{ height: effectiveHeight }}
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
