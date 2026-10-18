import type { LoadingTask } from './StockLoadingStatus'

export interface LoadingQueryState {
  isLoading: boolean
  isError: boolean
  refetch: () => unknown
}

export function buildLoadingTasks(queries: {
  detail: LoadingQueryState
  quote: LoadingQueryState
  klineFetchingCount: number
  sectors: LoadingQueryState
  financial: LoadingQueryState
  history: LoadingQueryState
  /** 无 research 权限时不传，任务整条隐藏 */
  research?: LoadingQueryState
  aiAnalysis: LoadingQueryState
}): LoadingTask[] {
  const { detail, quote, klineFetchingCount, sectors, financial, history, research, aiAnalysis } =
    queries
  const tasks: LoadingTask[] = [
    {
      key: 'detail',
      label: '股票详情',
      status: detail.isLoading ? 'loading' : detail.isError ? 'error' : 'idle',
      onRetry: () => detail.refetch(),
    },
    {
      key: 'quote',
      label: '实时行情',
      status: quote.isLoading ? 'loading' : quote.isError ? 'error' : 'idle',
      onRetry: () => quote.refetch(),
    },
    {
      key: 'kline',
      label: 'K线数据',
      status: klineFetchingCount > 0 ? 'loading' : 'idle',
    },
    {
      key: 'sectors',
      label: '所属板块',
      status: sectors.isLoading ? 'loading' : sectors.isError ? 'error' : 'idle',
      onRetry: () => sectors.refetch(),
    },
    {
      key: 'financial',
      label: '财务数据',
      status:
        financial.isLoading || history.isLoading
          ? 'loading'
          : financial.isError || history.isError
            ? 'error'
            : 'idle',
      onRetry: () => {
        financial.refetch()
        history.refetch()
      },
    },
    {
      key: 'ai-analysis',
      label: 'AI 分析',
      status: aiAnalysis.isLoading ? 'loading' : aiAnalysis.isError ? 'error' : 'idle',
      onRetry: () => aiAnalysis.refetch(),
    },
  ]
  return research
    ? [
        ...tasks.slice(0, -1),
        {
          key: 'research',
          label: '相关研报',
          status: research.isLoading ? 'loading' : research.isError ? 'error' : 'idle',
          onRetry: () => research.refetch(),
        },
        tasks[tasks.length - 1],
      ]
    : tasks
}
