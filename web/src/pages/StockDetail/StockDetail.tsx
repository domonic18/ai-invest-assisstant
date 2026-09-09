import { useIsFetching } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { useFinancial } from '@/hooks/useFinancial'
import { useFinancialHistory } from '@/hooks/useFinancialHistory'
import { queryKeys } from '@/hooks/queryKeys'
import { useResearch } from '@/hooks/useResearch'
import { useWatchlist } from '@/hooks/useWatchlist'
import {
  useStockAiAnalysis,
  useStockDetail,
  useStockQuote,
  useStockSectors,
} from '@/hooks/useStocks'
import { panelColors } from '@/theme/colors'
import { PAGE_SIZE, type StockQuote } from '@ai-invest/shared'

import { AddToWatchlistModal } from './components/AddToWatchlistModal'
import { ErrorState } from './components/ErrorState'
import { QuoteStrip } from './components/QuoteStrip'
import { StockChartArea } from './components/StockChartArea'
import { StockInfoPanel } from './components/StockInfoPanel'
import { buildLoadingTasks } from './loadingTasks'
import { StockLoadingStatus } from './StockLoadingStatus'

const PANEL_BG = panelColors.bg
const BORDER_COLOR = panelColors.border

/** 右栏收起态记忆（与左侧边栏折叠同样的持久化约定）。 */
const RIGHT_PANEL_COLLAPSED_KEY = 'ai-invest.stock-detail.right-panel.collapsed'

export function StockDetail() {
  const { code } = useParams<{ code?: string }>()
  const stockCode = code || ''

  const detailQ = useStockDetail(stockCode)
  const quoteQ = useStockQuote(stockCode)
  const sectorsQ = useStockSectors(stockCode)
  const financialQ = useFinancial(stockCode)
  const historyQ = useFinancialHistory(stockCode, 8)
  const researchQ = useResearch({ stockCode, pageSize: PAGE_SIZE.inline })
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

  const loadingTasks = buildLoadingTasks({
    detail: detailQ,
    quote: quoteQ,
    klineFetchingCount: klineFetching,
    sectors: sectorsQ,
    financial: financialQ,
    history: historyQ,
    research: researchQ,
    aiAnalysis: aiAnalysisQ,
  })

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
  const isWatched = watchlist?.some((item) => item.code === stockCode)

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

          <StockChartArea stockCode={stockCode} />
        </div>

        <StockInfoPanel
          stockCode={stockCode}
          collapsed={panelCollapsed}
          tasks={loadingTasks}
          onExpand={() => setPanelCollapsed(false)}
          onCollapse={() => setPanelCollapsed(true)}
        />
      </div>
    </div>
  )
}
