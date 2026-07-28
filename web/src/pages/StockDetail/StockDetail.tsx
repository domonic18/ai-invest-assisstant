import {
  FileTextOutlined,
  HeartOutlined,
  HeartTwoTone,
  WalletOutlined,
} from '@ant-design/icons'
import { Button, Empty, List, Select, Spin, Tabs, Tag, Typography } from 'antd'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'

import { StockChartView, type StockChartViewIndicators } from '@/components/charts/StockChartView'
import { FinancialTrendCharts } from '@/components/charts/FinancialTrendCharts'
import { useResearch } from '@/hooks/useResearch'
import { useStockDetail } from '@/hooks/useStocks'
import { useFinancial } from '@/hooks/useFinancial'
import { useFinancialHistory } from '@/hooks/useFinancialHistory'
import { useAddWatchlistItem, useWatchlist } from '@/hooks/useWatchlist'
import { StockQuoteHeader } from './StockQuoteHeader'
import { StockSectors } from './StockSectors'
import { FINANCIAL_METRIC_LABELS } from '@/constants/financial'
import { panelColors } from '@/theme/colors'
import type { ResearchReport } from '@ai-invest/shared'

const PANEL_BG = panelColors.bg
const BORDER_COLOR = panelColors.border

const STORAGE_KEY = 'ai-invest.stock-detail.views'

const DEFAULT_INDICATORS: StockChartViewIndicators = {
  volume: true,
  ma: true,
  macd: false,
  kdj: false,
}

interface ChartViewConfig {
  id: string
  period: string
  indicators: StockChartViewIndicators
}

type ViewPresetKey = 'daily-weekly' | 'daily-monthly' | 'daily' | 'weekly'

interface ViewPreset {
  key: ViewPresetKey
  label: string
  views: ChartViewConfig[]
}

const VIEW_PRESETS: ViewPreset[] = [
  {
    key: 'daily-weekly',
    label: '日线 + 周线',
    views: [
      { id: 'daily', period: 'daily', indicators: { ...DEFAULT_INDICATORS } },
      { id: 'weekly', period: 'weekly', indicators: { ...DEFAULT_INDICATORS } },
    ],
  },
  {
    key: 'daily-monthly',
    label: '日线 + 月线',
    views: [
      { id: 'daily', period: 'daily', indicators: { ...DEFAULT_INDICATORS } },
      { id: 'monthly', period: 'monthly', indicators: { ...DEFAULT_INDICATORS } },
    ],
  },
  {
    key: 'daily',
    label: '仅日线',
    views: [{ id: 'daily', period: 'daily', indicators: { ...DEFAULT_INDICATORS } }],
  },
  {
    key: 'weekly',
    label: '仅周线',
    views: [{ id: 'weekly', period: 'weekly', indicators: { ...DEFAULT_INDICATORS } }],
  },
]

const TOOLBAR_HEIGHT = 68
const MIN_CHART_HEIGHT = 180

function findPresetKey(views: ChartViewConfig[]): ViewPresetKey | 'custom' {
  for (const preset of VIEW_PRESETS) {
    if (
      views.length === preset.views.length &&
      views.every((v, i) => v.period === preset.views[i].period)
    ) {
      return preset.key
    }
  }
  return 'custom'
}

function StockFinancial({ code }: { code: string }) {
  const { data, isLoading } = useFinancial(code)
  const { data: historyData, isLoading: historyLoading } = useFinancialHistory(code, 8)

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spin size="small" />
      </div>
    )
  }

  if (!data) {
    return <Empty description="暂无财务数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  const renderPercent = (value: number | null) =>
    value === null ? '-' : `${(value * 100).toFixed(2)}%`

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-[#8c8c8c]">
        <span>报告期：{data.reportDate || '-'}</span>
        <span>类型：{data.reportType || '-'}</span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        {Object.entries(data.metrics).map(([key, value]) => (
          <div
            key={key}
            className="flex flex-col p-2 rounded"
            style={{ backgroundColor: '#14161c' }}
          >
            <span className="text-[10px] text-[#8c8c8c]">{FINANCIAL_METRIC_LABELS[key] || key}</span>
            <span className="text-sm text-[#d1d4dc] font-medium">{renderPercent(value)}</span>
          </div>
        ))}
      </div>

      {historyLoading ? (
        <div className="flex justify-center py-6">
          <Spin size="small" />
        </div>
      ) : historyData?.history.length ? (
        <FinancialTrendCharts history={historyData.history} />
      ) : (
        <Empty description="暂无历史财务趋势" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </div>
  )
}

function StockResearch({ code }: { code: string }) {
  const { data, isLoading } = useResearch({ stockCode: code, pageSize: 5 })

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spin size="small" />
      </div>
    )
  }

  if (!data?.items.length) {
    return <Empty description="暂无相关研报" image={Empty.PRESENTED_IMAGE_SIMPLE} />
  }

  return (
    <List
      dataSource={data.items}
      renderItem={(item: ResearchReport) => (
        <List.Item className="!border-b-[#23262e]">
          <List.Item.Meta
            title={
              <span className="text-[#d1d4dc] text-sm">{item.title}</span>
            }
            description={
              <div className="space-y-1">
                <span className="text-xs text-[#8c8c8c]">
                  {item.source || '未知来源'} · {item.publishDate || '-'}
                </span>
                {item.summary && (
                  <Typography.Paragraph className="!text-xs text-[#8c8c8c] !mb-0">
                    {item.summary}
                  </Typography.Paragraph>
                )}
              </div>
            }
          />
        </List.Item>
      )}
    />
  )
}

interface StockHeaderProps {
  stock: {
    name: string
    code: string
    market: string
    industry?: string | null
  }
  stockCode: string
  isWatched?: boolean
  onToggleWatchlist: () => void
  isLoading?: boolean
}

function StockHeader({ stock, stockCode, isWatched, onToggleWatchlist, isLoading }: StockHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <Typography.Title level={5} className="!mb-0 text-[#d1d4dc]">
          {stock.name}
        </Typography.Title>
        <span className="text-sm text-[#8c8c8c]">{stockCode}</span>
        <Tag color="blue" className="!text-xs">{stock.market}</Tag>
        {stock.industry && <Tag className="!text-xs">{stock.industry}</Tag>}
      </div>
      <Button
        type={isWatched ? 'default' : 'primary'}
        size="small"
        icon={isWatched ? <HeartTwoTone twoToneColor="#eb2f96" /> : <HeartOutlined />}
        onClick={onToggleWatchlist}
        loading={isLoading}
        disabled={isWatched}
      >
        {isWatched ? '已加入自选' : '加入自选'}
      </Button>
    </div>
  )
}

export function StockDetail() {
  const { code } = useParams<{ code?: string }>()
  const stockCode = code || ''

  const { data: stock, isLoading: stockLoading } = useStockDetail(stockCode)
  const { data: watchlist } = useWatchlist()
  const addMutation = useAddWatchlistItem()

  const [views, setViews] = useState<ChartViewConfig[]>(VIEW_PRESETS[0].views)
  const [presetKey, setPresetKey] = useState<ViewPresetKey | 'custom'>('daily-weekly')
  const [viewsLoaded, setViewsLoaded] = useState(false)

  const storageKey = useMemo(() => `${STORAGE_KEY}.${stockCode}`, [stockCode])

  useEffect(() => {
    if (!stockCode) return
    try {
      const rawViews = localStorage.getItem(storageKey)
      const rawPreset = localStorage.getItem(`${storageKey}.preset`)
      let initialViews = VIEW_PRESETS[0].views
      if (rawViews) {
        const parsed = JSON.parse(rawViews) as ChartViewConfig[]
        if (Array.isArray(parsed) && parsed.length > 0) {
          initialViews = parsed
        }
      }
      setViews(initialViews)
      if (rawPreset && VIEW_PRESETS.some((p) => p.key === rawPreset)) {
        setPresetKey(rawPreset as ViewPresetKey)
      } else {
        setPresetKey(findPresetKey(initialViews))
      }
    } catch {
      setViews(VIEW_PRESETS[0].views)
      setPresetKey('daily-weekly')
    }
    setViewsLoaded(true)
  }, [storageKey, stockCode])

  useEffect(() => {
    if (!viewsLoaded) return
    try {
      localStorage.setItem(storageKey, JSON.stringify(views))
      localStorage.setItem(`${storageKey}.preset`, presetKey)
    } catch {
      // ignore storage errors
    }
  }, [views, presetKey, viewsLoaded, storageKey])

  useEffect(() => {
    setPresetKey(findPresetKey(views))
  }, [views])

  const isWatched = watchlist?.some((item) => item.code === stockCode)

  const handleToggleWatchlist = () => {
    if (!isWatched) {
      addMutation.mutate({ stockCode, tags: [] })
    }
  }

  const handlePresetChange = (value: ViewPresetKey | 'custom') => {
    const preset = VIEW_PRESETS.find((p) => p.key === value)
    if (!preset) return
    setPresetKey(value)
    setViews(preset.views.map((v) => ({ ...v })))
  }

  const updateView = (id: string, patch: Partial<ChartViewConfig>) => {
    setViews((prev) => prev.map((v) => (v.id === id ? { ...v, ...patch } : v)))
  }

  const chartContainerRef = useRef<HTMLDivElement>(null)
  const [containerHeight, setContainerHeight] = useState(600)

  useEffect(() => {
    const el = chartContainerRef.current
    if (!el) return

    const updateHeight = () => {
      setContainerHeight(el.clientHeight)
    }
    updateHeight()

    let ro: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(updateHeight)
      ro.observe(el)
    } else {
      window.addEventListener('resize', updateHeight)
    }

    return () => {
      ro?.disconnect()
      window.removeEventListener('resize', updateHeight)
    }
  }, [])

  const chartHeight = useMemo(() => {
    return Math.max(MIN_CHART_HEIGHT, Math.floor(containerHeight / views.length) - TOOLBAR_HEIGHT)
  }, [containerHeight, views.length])

  if (stockLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spin size="large" />
      </div>
    )
  }

  if (!stock) {
    return <Typography.Text type="danger">未找到股票 {stockCode}</Typography.Text>
  }

  const rightTabItems = [
    {
      key: 'financial',
      label: (
        <span className="text-xs">
          <WalletOutlined className="mr-1" />
          财务
        </span>
      ),
      children: <StockFinancial code={stockCode} />,
    },
    {
      key: 'research',
      label: (
        <span className="text-xs">
          <FileTextOutlined className="mr-1" />
          研报
        </span>
      ),
      children: <StockResearch code={stockCode} />,
    },
    {
      key: 'news',
      label: <span className="text-xs">相关新闻</span>,
      children: (
        <Typography.Text type="secondary" className="text-xs">
          相关新闻功能开发中，敬请期待。
        </Typography.Text>
      ),
    },
  ]

  const headerContent = (
    <StockHeader
      stock={stock}
      stockCode={stockCode}
      isWatched={isWatched}
      onToggleWatchlist={handleToggleWatchlist}
      isLoading={addMutation.isPending}
    />
  )

  return (
    <div className="flex flex-col h-full">
      {/* Mobile-only header */}
      <div
        className="lg:hidden px-4 py-3"
        style={{ borderBottom: `1px solid ${BORDER_COLOR}`, backgroundColor: PANEL_BG }}
      >
        {headerContent}
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Center: charts */}
        <div className="flex-1 flex flex-col min-w-0">
          <div
            className="flex items-center justify-between px-3 py-2"
            style={{ borderBottom: `1px solid ${BORDER_COLOR}`, backgroundColor: PANEL_BG }}
          >
            <span className="text-sm font-medium text-[#d1d4dc]">多周期 K 线</span>
            <Select<ViewPresetKey | 'custom'>
              value={presetKey}
              onChange={handlePresetChange}
              options={[
                ...VIEW_PRESETS.map((p) => ({ value: p.key, label: p.label })),
                { value: 'custom' as const, label: '自定义' },
              ]}
              size="small"
              className="w-36"
            />
          </div>

          <div
            ref={chartContainerRef}
            className="flex-1 overflow-hidden flex flex-col"
            style={{ backgroundColor: '#050608' }}
          >
            {views.map((view) => (
              <StockChartView
                key={view.id}
                code={stockCode}
                defaultPeriod={view.period}
                defaultIndicators={view.indicators}
                onPeriodChange={(period) => updateView(view.id, { period })}
                onIndicatorsChange={(indicators) => updateView(view.id, { indicators })}
                height={chartHeight}
              />
            ))}
          </div>
        </div>

        {/* Right: info panel */}
        <div
          className="hidden lg:flex lg:flex-col lg:w-80 shrink-0 overflow-y-auto"
          style={{ borderLeft: `1px solid ${BORDER_COLOR}`, backgroundColor: PANEL_BG }}
        >
          <div className="px-3 py-3" style={{ borderBottom: `1px solid ${BORDER_COLOR}` }}>
            {headerContent}
          </div>

          <div style={{ borderBottom: `1px solid ${BORDER_COLOR}` }}>
            <StockQuoteHeader code={stockCode} />
          </div>

          <div style={{ borderBottom: `1px solid ${BORDER_COLOR}` }}>
            <StockSectors code={stockCode} />
          </div>

          <div className="flex-1 p-3">
            <Tabs
              defaultActiveKey="financial"
              items={rightTabItems}
              className="stock-detail-tabs"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
