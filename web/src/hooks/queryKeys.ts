/**
 * 全站 TanStack Query 缓存键工厂。
 *
 * 约定:
 * - 每个 domain 一个 namespace (market / stocks / chain / ...)
 * - namespace 内 `all` 用于整体 invalidate,其它方法构造具体 key
 * - 新代码必须经此工厂获取 queryKey,避免散落字面量
 */
export const queryKeys = {
  admin: {
    news: ['admin-news'] as const,
    reports: ['admin-reports'] as const,
    stocks: ['admin-stocks'] as const,
    users: ['admin-users'] as const,
    tasks: ['admin-tasks'] as const,
  },
  auction: {
    all: ['auction'] as const,
    indexTrend: (days: number, startDate?: string, endDate?: string) =>
      ['auction', 'index-trend', days, startDate, endDate] as const,
  },
  chain: {
    all: ['chain'] as const,
    analysis: (industry: string) => ['chain', 'analysis', industry] as const,
    latest: (industry: string) => ['chain', 'latest', industry] as const,
    versions: (industry: string) => ['chain', 'versions', industry] as const,
    version: (industry: string, versionId: number) =>
      ['chain', 'version', industry, versionId] as const,
  },
  calendar: {
    all: ['calendar'] as const,
    events: (start: string, end: string) => ['calendar', 'events', start, end] as const,
    upcoming: (limit: number) => ['calendar', 'upcoming', limit] as const,
  },
  collector: {
    logs: ['collector-logs'] as const,
    taskCatalog: ['collector-task-catalog'] as const,
    taskChannels: (taskName: string) => ['collector-task-channels', taskName] as const,
    channels: ['collector-channel-configs'] as const,
    dataTypes: ['collector-data-type-channels'] as const,
  },
  financial: {
    all: ['financial'] as const,
    history: (code: string, limit: number) =>
      ['financial-history', code, limit] as const,
  },
  financialReports: {
    all: ['financial-reports'] as const,
  },
  fundFlow: {
    all: ['fund-flow'] as const,
    sectorTrend: (sectorType: string, days: number) =>
      ['fund-flow', 'sector-trend', sectorType, days] as const,
  },
  hotspot: ['hotspot'] as const,
  llmConfigs: ['llm-configs'] as const,
  trackedIndexes: ['tracked-indexes'] as const,
  market: {
    all: ['market'] as const,
    indices: (tradeDate?: string) => ['market', 'indices', tradeDate] as const,
    intraday: (code: string, tradeDate?: string) =>
      ['market', 'intraday', code, tradeDate] as const,
    kline: (code: string, period: string) => ['market', 'kline', code, period] as const,
    stats: (tradeDate?: string) => ['market', 'stats', tradeDate] as const,
    limitUp: (tradeDate?: string) => ['market', 'limit-up', tradeDate] as const,
    limitUpIntraday: (tradeDate?: string) =>
      ['market', 'limit-up-intraday', tradeDate] as const,
    sectors: (tradeDate?: string) => ['market', 'sectors', tradeDate] as const,
    watchlistQuotes: ['market', 'watchlist-quotes'] as const,
    aiReview: (tradeDate?: string) => ['market', 'ai-review', tradeDate] as const,
  },
  research: {
    all: ['research'] as const,
    filters: ['research', 'filters'] as const,
  },
  stocks: {
    all: ['stocks'] as const,
    search: (q: string) => ['stocks', 'search', q] as const,
    detail: (code: string) => ['stocks', 'detail', code] as const,
    quote: (code: string) => ['stocks', 'quote', code] as const,
    kline: (code: string, period?: string, limit?: number) =>
      ['stocks', 'kline', code, period, limit] as const,
    klinePaged: (code: string, pageSize: number) =>
      ['stocks', 'kline', code, pageSize] as const,
    intraday: (code: string, tradeDate?: string) =>
      ['stocks', 'intraday', code, tradeDate] as const,
    sectors: (code: string) => ['stocks', 'sectors', code] as const,
    aiAnalysis: (code: string, tradeDate?: string) =>
      ['stocks', 'ai-analysis', code, tradeDate] as const,
    aiAnalysisDates: (code: string) => ['stocks', 'ai-analysis-dates', code] as const,
  },
  watchlist: {
    all: ['watchlist'] as const,
    groups: ['watchlist', 'groups'] as const,
    items: ['watchlist', 'items'] as const,
  },
  telegraph: {
    all: ['telegraph'] as const,
    list: (page: number, pageSize: number, minImportance?: number) =>
      ['telegraph', 'list', page, pageSize, minImportance ?? 0] as const,
  },
  workbench: {
    all: ['workbench'] as const,
    overview: ['workbench', 'overview'] as const,
  },
} as const
