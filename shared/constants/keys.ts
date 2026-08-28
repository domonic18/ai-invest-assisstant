/** TanStack Query keys grouped by feature domain. */
export const QueryKey = {
  market: {
    index: 'market-index',
    breadth: 'market-breadth',
    limitUp: 'market-limit-up',
  },
  stock: {
    detail: (code: string) => ['stock', code],
    kline: (code: string, period: string) => ['stock', code, 'kline', period],
  },
  chain: {
    analysis: 'chain-analysis',
    versions: 'chain-versions',
  },
  report: {
    list: 'report-list',
  },
  financial: {
    report: 'financial-report',
  },
} as const

/** Local storage keys. */
export const StorageKey = {
  assistant: {
    sidebarWidth: 'assistant:sidebar-width',
    threadId: 'assistant:thread-id',
  },
  settings: {
    indicators: 'settings:indicators',
  },
} as const
