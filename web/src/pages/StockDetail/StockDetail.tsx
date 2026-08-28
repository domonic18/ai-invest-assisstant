import { FileTextOutlined, WalletOutlined } from '@ant-design/icons'
import { useIsFetching } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'

import { Select, Tabs } from 'antd'

import { StockChartView } from '@/components/charts/StockChartView'
import { useFinancial } from '@/hooks/useFinancial'
import { useFinancialHistory } from '@/hooks/useFinancialHistory'
import { useResearch } from '@/hooks/useResearch'
import { useAddWatchlistItem, useWatchlist } from '@/hooks/useWatchlist'
import {
  useStockDetail,
  useStockQuote,
  useStockSectors,
} from '@/hooks/useStocks'
import { queryKeys } from '@/hooks/queryKeys'
import { panelColors } from '@/theme/colors'
import type { StockQuote, StockSector } from '@ai-invest/shared'

import {
  type ChartViewConfig,
  findPresetKey,
  MIN_CHART_HEIGHT,
  STORAGE_KEY,
  TOOLBAR_HEIGHT,
  VIEW_PRESETS,
  type ViewPresetKey,
} from './chartConfig'
import { ErrorState } from './components/ErrorState'
import { StockFinancial } from './components/StockFinancial'
import { StockHeader } from './components/StockHeader'
import { StockResearch } from './components/StockResearch'
import { StockLoadingStatus, type LoadingTask } from './StockLoadingStatus'
import { StockQuoteHeader } from './StockQuoteHeader'
import { StockSectors } from './StockSectors'

type StockSectorsData = { code: string; name: string; sectors: StockSector[] }

const PANEL_BG = panelColors.bg
const BORDER_COLOR = panelColors.border

export function StockDetail() {
  const { code } = useParams<{ code?: string }>()
  const stockCode = code || ''

  const detailQ = useStockDetail(stockCode)
  const quoteQ = useStockQuote(stockCode)
  const sectorsQ = useStockSectors(stockCode)
  const financialQ = useFinancial(stockCode)
  const historyQ = useFinancialHistory(stockCode, 8)
  const researchQ = useResearch({ stockCode, pageSize: 5 })
  const { data: watchlist } = useWatchlist()
  const addMutation = useAddWatchlistItem()

  const klineFetching = useIsFetching({
    queryKey: queryKeys.stocks.kline(stockCode),
  })

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

  const loadingTasks: LoadingTask[] = [
    {
      key: 'detail',
      label: '股票详情',
      status: detailQ.isLoading ? 'loading' : detailQ.isError ? 'error' : 'idle',
      onRetry: () => detailQ.refetch(),
    },
    {
      key: 'quote',
      label: '实时行情',
      status: quoteQ.isLoading ? 'loading' : quoteQ.isError ? 'error' : 'idle',
      onRetry: () => quoteQ.refetch(),
    },
    {
      key: 'kline',
      label: 'K线数据',
      status: klineFetching > 0 ? 'loading' : 'idle',
    },
    {
      key: 'sectors',
      label: '所属板块',
      status: sectorsQ.isLoading ? 'loading' : sectorsQ.isError ? 'error' : 'idle',
      onRetry: () => sectorsQ.refetch(),
    },
    {
      key: 'financial',
      label: '财务数据',
      status:
        financialQ.isLoading || historyQ.isLoading
          ? 'loading'
          : financialQ.isError || historyQ.isError
            ? 'error'
            : 'idle',
      onRetry: () => {
        financialQ.refetch()
        historyQ.refetch()
      },
    },
    {
      key: 'research',
      label: '相关研报',
      status: researchQ.isLoading ? 'loading' : researchQ.isError ? 'error' : 'idle',
      onRetry: () => researchQ.refetch(),
    },
  ]

  if (!stockCode) {
    return <ErrorState message="未指定股票代码" />
  }

  if (detailQ.isError) {
    return (
      <ErrorState
        message={`股票详情加载失败：${detailQ.error instanceof Error ? detailQ.error.message : '请稍后重试'}`}
        onRetry={() => detailQ.refetch()}
        isRetrying={detailQ.isFetching}
      />
    )
  }

  const stock = detailQ.data
  const quote: StockQuote | undefined = quoteQ.data
  const sectors: StockSectorsData | undefined = sectorsQ.data

  const rightTabItems = [
    {
      key: 'financial',
      label: (
        <span className="text-xs">
          <WalletOutlined className="mr-1" />
          财务
        </span>
      ),
      children: (
        <StockFinancial
          data={financialQ.data}
          history={historyQ.data}
          isLoading={financialQ.isLoading}
          historyLoading={historyQ.isLoading}
          isError={financialQ.isError}
          historyError={historyQ.isError}
          onRetry={() => {
            financialQ.refetch()
            historyQ.refetch()
          }}
        />
      ),
    },
    {
      key: 'research',
      label: (
        <span className="text-xs">
          <FileTextOutlined className="mr-1" />
          研报
        </span>
      ),
      children: (
        <StockResearch
          data={researchQ.data}
          isLoading={researchQ.isLoading}
          isError={researchQ.isError}
          onRetry={() => researchQ.refetch()}
        />
      ),
    },
    {
      key: 'news',
      label: <span className="text-xs">相关新闻</span>,
      children: (
        <span className="text-xs text-[#8c8c8c]">
          相关新闻功能开发中，敬请期待。
        </span>
      ),
    },
  ]

  const headerContent = (
    <StockHeader
      stock={stock}
      stockCode={stockCode}
      isWatched={isWatched}
      onToggleWatchlist={handleToggleWatchlist}
      isWatchlistLoading={addMutation.isPending}
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

      {/* Mobile loading status (mirrors right-panel status on small screens) */}
      <div className="lg:hidden">
        <StockLoadingStatus tasks={loadingTasks} />
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

          <StockLoadingStatus tasks={loadingTasks} />

          <div style={{ borderBottom: `1px solid ${BORDER_COLOR}` }}>
            <StockQuoteHeader
              quote={quote}
              isLoading={quoteQ.isLoading}
              isError={quoteQ.isError}
              onRetry={() => quoteQ.refetch()}
            />
          </div>

          <div style={{ borderBottom: `1px solid ${BORDER_COLOR}` }}>
            <StockSectors
              sectors={sectors}
              isLoading={sectorsQ.isLoading}
              isError={sectorsQ.isError}
              onRetry={() => sectorsQ.refetch()}
            />
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
