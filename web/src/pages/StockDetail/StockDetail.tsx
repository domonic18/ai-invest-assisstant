import {
  AppstoreOutlined,
  DoubleLeftOutlined,
  DoubleRightOutlined,
  FileTextOutlined,
  RobotOutlined,
  WalletOutlined,
} from '@ant-design/icons'
import { useIsFetching } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'

import { Tabs } from 'antd'

import { StockChartView } from '@/components/charts/stockChartView'
import { useFinancial } from '@/hooks/useFinancial'
import { useFinancialHistory } from '@/hooks/useFinancialHistory'
import { useResearch } from '@/hooks/useResearch'
import { useWatchlist } from '@/hooks/useWatchlist'
import {
  useStockAiAnalysis,
  useStockDetail,
  useStockQuote,
  useStockSectors,
} from '@/hooks/useStocks'
import { queryKeys } from '@/hooks/queryKeys'
import { panelColors } from '@/theme/colors'
import type { StockQuote, StockSector } from '@ai-invest/shared'

import {
  buildViews,
  type ChartViewConfig,
  DEFAULT_INDICATORS,
  MIN_CHART_HEIGHT,
  STORAGE_KEY,
  TOOLBAR_HEIGHT,
} from './chartConfig'
import { AddToWatchlistModal } from './components/AddToWatchlistModal'
import { ErrorState } from './components/ErrorState'
import { QuoteStrip } from './components/QuoteStrip'
import { StockAiAnalysisSection } from './components/StockAiAnalysisSection'
import { StockFinancial } from './components/StockFinancial'
import { StockResearch } from './components/StockResearch'
import { StockLoadingStatus, type LoadingTask } from './StockLoadingStatus'
import { StockSectors } from './StockSectors'

type StockSectorsData = { code: string; name: string; sectors: StockSector[] }

const PANEL_BG = panelColors.bg
const BORDER_COLOR = panelColors.border

/** 右栏收起态记忆（与左侧边栏折叠同样的持久化约定）。 */
const RIGHT_PANEL_COLLAPSED_KEY = 'ai-invest.stock-detail.right-panel.collapsed'

/** 双图加权分配：上 58 / 下 42，与原型一致。 */
const DUAL_VIEW_WEIGHTS = [0.58, 0.42]

function normalizeViews(parsed: unknown): ChartViewConfig[] | null {
  if (!Array.isArray(parsed) || parsed.length === 0) return null
  return (parsed as ChartViewConfig[]).map((v) => ({
    ...v,
    indicators: { ...DEFAULT_INDICATORS, ...v.indicators },
  }))
}

export function StockDetail() {
  const { code } = useParams<{ code?: string }>()
  const stockCode = code || ''

  const detailQ = useStockDetail(stockCode)
  const quoteQ = useStockQuote(stockCode)
  const sectorsQ = useStockSectors(stockCode)
  const financialQ = useFinancial(stockCode)
  const historyQ = useFinancialHistory(stockCode, 8)
  const researchQ = useResearch({ stockCode, pageSize: 5 })
  const aiAnalysisQ = useStockAiAnalysis(stockCode)
  const { data: watchlist } = useWatchlist()

  const [addWatchOpen, setAddWatchOpen] = useState(false)
  const [panelCollapsed, setPanelCollapsed] = useState(
    () => localStorage.getItem(RIGHT_PANEL_COLLAPSED_KEY) === '1',
  )

  useEffect(() => {
    try {
      localStorage.setItem(RIGHT_PANEL_COLLAPSED_KEY, panelCollapsed ? '1' : '0')
    } catch {
      // ignore storage errors
    }
  }, [panelCollapsed])

  const klineFetching = useIsFetching({
    queryKey: queryKeys.stocks.kline(stockCode),
  })

  const [views, setViews] = useState<ChartViewConfig[]>(() => buildViews(true))
  const [dual, setDual] = useState(true)
  const [viewsLoaded, setViewsLoaded] = useState(false)

  const storageKey = useMemo(() => `${STORAGE_KEY}.${stockCode}`, [stockCode])

  useEffect(() => {
    if (!stockCode) return
    try {
      const rawViews = localStorage.getItem(storageKey)
      const rawDual = localStorage.getItem(`${storageKey}.dual`)
      const nextDual = rawDual !== '0'
      const parsed = rawViews ? normalizeViews(JSON.parse(rawViews)) : null
      setDual(nextDual)
      setViews(parsed ?? buildViews(nextDual))
    } catch {
      setDual(true)
      setViews(buildViews(true))
    }
    setViewsLoaded(true)
  }, [storageKey, stockCode])

  useEffect(() => {
    if (!viewsLoaded) return
    try {
      localStorage.setItem(storageKey, JSON.stringify(views))
      localStorage.setItem(`${storageKey}.dual`, dual ? '1' : '0')
    } catch {
      // ignore storage errors
    }
  }, [views, dual, viewsLoaded, storageKey])

  const isWatched = watchlist?.some((item) => item.code === stockCode)

  const handleDualChange = (next: boolean) => {
    setDual(next)
    setViews((prev) => {
      if (next) {
        if (prev.length === 2) return prev
        const weekly = buildViews(true).find((v) => v.id === 'weekly')
        return weekly ? [...prev, { ...weekly }] : prev
      }
      return prev.filter((v) => v.id === 'daily')
    })
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

  const viewHeights = useMemo(() => {
    if (views.length === 2) {
      return DUAL_VIEW_WEIGHTS.map(
        (w) => Math.max(MIN_CHART_HEIGHT, Math.floor(containerHeight * w) - TOOLBAR_HEIGHT),
      )
    }
    const each = Math.max(
      MIN_CHART_HEIGHT,
      Math.floor(containerHeight / views.length) - TOOLBAR_HEIGHT,
    )
    return Array.from({ length: views.length }, () => each)
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
    {
      key: 'ai-analysis',
      label: 'AI 分析',
      status: aiAnalysisQ.isLoading ? 'loading' : aiAnalysisQ.isError ? 'error' : 'idle',
      onRetry: () => aiAnalysisQ.refetch(),
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

  const sectorTabChildren = (
    <StockSectors
      sectors={sectors}
      stock={stock}
      isLoading={sectorsQ.isLoading}
      isError={sectorsQ.isError}
      onRetry={() => sectorsQ.refetch()}
    />
  )

  const rightTabItems = [
    {
      key: 'ai',
      label: (
        <span className="text-xs">
          <RobotOutlined className="mr-1" />
          AI 分析
        </span>
      ),
      children: <StockAiAnalysisSection stockCode={stockCode} />,
    },
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
      key: 'sector',
      label: (
        <span className="text-xs">
          <AppstoreOutlined className="mr-1" />
          板块
        </span>
      ),
      children: sectorTabChildren,
    },
  ]

  return (
    <div className="flex flex-col h-full">
      <AddToWatchlistModal
        open={addWatchOpen}
        stockCode={stockCode}
        onClose={() => setAddWatchOpen(false)}
      />

      {/* Mobile loading status (mirrors right-panel status on small screens) */}
      <div className="lg:hidden">
        <StockLoadingStatus tasks={loadingTasks} />
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Center: quote strip + charts */}
        <div className="flex-1 flex flex-col min-w-0">
          <div
            className="shrink-0"
            style={{ borderBottom: `1px solid ${BORDER_COLOR}`, backgroundColor: PANEL_BG }}
          >
            <QuoteStrip
              stockCode={stockCode}
              stock={stock}
              stockLoading={detailQ.isLoading}
              quote={quote}
              quoteLoading={quoteQ.isLoading}
              isWatched={isWatched}
              onAddWatchlist={() => setAddWatchOpen(true)}
            />
          </div>

          <div
            ref={chartContainerRef}
            className="flex-1 overflow-hidden flex flex-col"
            style={{ backgroundColor: '#050608' }}
          >
            {views.map((view, i) => (
              <StockChartView
                key={view.id}
                code={stockCode}
                defaultPeriod={view.period}
                defaultIndicators={view.indicators}
                onPeriodChange={(period) => updateView(view.id, { period })}
                onIndicatorsChange={(indicators) => updateView(view.id, { indicators })}
                height={viewHeights[i] ?? MIN_CHART_HEIGHT}
                layoutToggle={i === 0 ? { value: dual, onChange: handleDualChange } : undefined}
              />
            ))}
          </div>
        </div>

        {/* Right: info panel */}
        <div
          className="hidden lg:flex lg:flex-col shrink-0 overflow-hidden"
          style={{
            borderLeft: `1px solid ${BORDER_COLOR}`,
            backgroundColor: PANEL_BG,
            width: panelCollapsed ? 36 : 360,
          }}
        >
          {panelCollapsed ? (
            <button
              type="button"
              title="展开信息面板"
              onClick={() => setPanelCollapsed(false)}
              className="w-full h-9 flex items-center justify-center text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
            >
              <DoubleLeftOutlined />
            </button>
          ) : (
            <>
              <StockLoadingStatus tasks={loadingTasks} />

              <div className="flex-1 overflow-y-auto p-3">
                <Tabs
                  defaultActiveKey="ai"
                  items={rightTabItems}
                  className="stock-detail-tabs"
                  tabBarExtraContent={{
                    right: (
                      <button
                        type="button"
                        title="收起信息面板"
                        onClick={() => setPanelCollapsed(true)}
                        className="flex items-center justify-center w-6 h-6 rounded text-[#8a8f98] transition-colors hover:bg-[#1c1f26] hover:text-[#f0f1f5]"
                      >
                        <DoubleRightOutlined className="!text-[12px]" />
                      </button>
                    ),
                  }}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
