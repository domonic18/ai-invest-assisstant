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
    telegraph: ['admin-telegraph'] as const,
    reports: ['admin-reports'] as const,
    stocks: ['admin-stocks'] as const,
    users: ['admin-users'] as const,
    tasks: ['admin-tasks'] as const,
    aiResults: ['admin-ai-results'] as const,
    aiResultSkills: ['admin-ai-result-skills'] as const,
    pendingApplications: ['admin-pending-applications'] as const,
    pendingCount: ['admin-pending-count'] as const,
    usageDashboard: (days: number) => ['admin-usage-dashboard', days] as const,
    usagePerUsers: (days: number) => ['admin-usage-per-users', days] as const,
    accountSettings: ['admin-account-settings'] as const,
    systemStatus: ['admin-system-status'] as const,
  },
  auction: {
    all: ['auction'] as const,
    indexTrend: (days: number, startDate?: string, endDate?: string) =>
      ['auction', 'index-trend', days, startDate, endDate] as const,
  },
  skills: {
    all: ['skills'] as const,
    square: ['skills', 'square'] as const,
    detail: (skillId: string) => ['skills', 'detail', skillId] as const,
    files: (skillId: string) => ['skills', 'files', skillId] as const,
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
    logSummary: ['collector-log-summary'] as const,
    taskCatalog: ['collector-task-catalog'] as const,
    taskChannels: (taskName: string) => ['collector-task-channels', taskName] as const,
    channels: ['collector-channel-configs'] as const,
    dataTypes: ['collector-data-type-channels'] as const,
    healthAll: ['collector-health'] as const,
    healthOverview: ['collector-health', 'overview'] as const,
    healthTasks: (domain: string | null, status: string | null) =>
      ['collector-health', 'tasks', domain, status] as const,
    healthChannels: ['collector-health', 'channels'] as const,
    healthScheduleCheck: (date: string) => ['collector-health', 'schedule-check', date] as const,
  },
  financial: {
    all: ['financial'] as const,
    history: (code: string, limit: number) =>
      ['financial-history', code, limit] as const,
  },
  financialReports: {
    all: ['financial-reports'] as const,
    list: (stockCode: string, pageSize: number) =>
      ['financial-reports', stockCode, pageSize] as const,
  },
  fundFlow: {
    all: ['fund-flow'] as const,
    sectorTrend: (sectorType: string, days: number) =>
      ['fund-flow', 'sector-trend', sectorType, days] as const,
  },
  anomaly: {
    all: ['anomaly'] as const,
    sector: (tradeDate?: string, sectorType?: string) =>
      ['anomaly', 'sector', tradeDate ?? null, sectorType ?? null] as const,
    sectorDates: ['anomaly', 'sector-dates'] as const,
    stock: (tradeDate?: string) => ['anomaly', 'stock', tradeDate ?? null] as const,
    stockDates: ['anomaly', 'stock-dates'] as const,
  },
  sectorDetail: (sectorType: string, sectorCode: string) =>
    ['sector-detail', sectorType, sectorCode] as const,
  hotspot: ['hotspot'] as const,
  account: {
    all: ['account'] as const,
    quota: ['account', 'quota'] as const,
    usage: (feature?: string) => ['account', 'usage', feature ?? null] as const,
    llmConfig: ['account', 'llm-config'] as const,
  },
  llmConfigs: ['llm-configs'] as const,
  kb: {
    all: ['kb'] as const,
    settings: ['kb', 'settings'] as const,
    sources: ['kb', 'sources'] as const,
    media: (sourceId: number) => ['kb', 'media', sourceId] as const,
    transcript: (sourceId: number, mediaId: number) =>
      ['kb', 'transcript', sourceId, mediaId] as const,
    chapters: (sourceId: number) => ['kb', 'chapters', sourceId] as const,
    points: (sourceId: number, status: string | null, page: number, pageSize: number) =>
      ['kb', 'points', sourceId, status, page, pageSize] as const,
    images: (
      sourceId: number,
      mediaId: number | null,
      status: string | null,
      page: number,
      pageSize: number
    ) => ['kb', 'images', sourceId, mediaId, status, page, pageSize] as const,
    search: (q: string, sourceId: number | null, chapterPath: string[], kind: string | null) =>
      ['kb', 'search', q, sourceId, chapterPath, kind] as const,
    chaptersPublished: (sourceId: number) =>
      ['kb', 'chapters-published', sourceId] as const,
  },
  mcpServers: ['mcp-servers'] as const,
  socialAdmin: {
    accounts: (page: number, pageSize: number) =>
      ['admin-social-accounts', page, pageSize] as const,
    accountPosts: (accountId: number) =>
      ['admin-social-account-posts', accountId] as const,
    status: ['admin-social-status'] as const,
    asrConfig: ['admin-social-asr-config'] as const,
  },
  proxyConfigs: ['proxy-configs'] as const,
  trackedIndexOptions: ['tracked-index-options'] as const,
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
    aiReviewDates: ['market', 'ai-review-dates'] as const,
    globalIndices: ['market', 'global-indices'] as const,
    globalIndexHistory: (indexCode: string, months: number) =>
      ['market', 'global-index-history', indexCode, months] as const,
    globalIndexKline: (indexCode: string, period: string) =>
      ['market', 'global-index-kline', indexCode, period] as const,
    fedWatch: ['market', 'fed-watch'] as const,
    sectorQuotes: (sectorType: string) =>
      ['market', 'sector-quotes', sectorType] as const,
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
    list: (
      page: number,
      pageSize: number,
      minImportance?: number,
      minAiScore?: number,
      subscriptionOnly?: boolean,
    ) =>
      [
        'telegraph',
        'list',
        page,
        pageSize,
        minImportance ?? 0,
        minAiScore ?? null,
        subscriptionOnly ?? false,
      ] as const,
  },
  news: {
    all: ['news'] as const,
    channels: ['news', 'channels'] as const,
    flash: (page: number, pageSize: number) =>
      ['news', 'flash', page, pageSize] as const,
    focus: ['news', 'focus'] as const,
    topics: (sessionKey: string) => ['news', 'topics', sessionKey] as const,
    story: (id: number) => ['news', 'story', id] as const,
    subscriptions: ['news', 'subscriptions'] as const,
  },
  social: {
    all: ['social'] as const,
    feed: (page: number, pageSize: number, filterKey: string) =>
      ['social', 'feed', page, pageSize, filterKey] as const,
    accounts: ['social', 'accounts'] as const,
    timeline: (accountId: number, page: number, pageSize: number) =>
      ['social', 'timeline', accountId, page, pageSize] as const,
  },
  users: {
    all: ['users'] as const,
    me: ['users', 'me'] as const,
  },
  workbench: {
    all: ['workbench'] as const,
    overview: ['workbench', 'overview'] as const,
    reviewStatus: ['workbench', 'reviewStatus'] as const,
  },
  klineDrawings: {
    /** 全周期画线（period 为归属键，周期切换前端过滤） */
    target: (targetType: string, targetCode: string) =>
      ['kline-drawings', targetType, targetCode] as const,
  },
} as const
