export const API_BASE = '/api/v1'

export const ENDPOINTS = {
  auth: {
    register: `${API_BASE}/auth/register`,
    login: `${API_BASE}/auth/login`,
    wxLogin: `${API_BASE}/auth/wx-login`,
  },
  users: {
    me: `${API_BASE}/users/me`,
    mePassword: `${API_BASE}/users/me/password`,
    meSettings: `${API_BASE}/users/me/settings`,
    watchlist: `${API_BASE}/users/watchlist`,
    watchlistQuotes: `${API_BASE}/users/watchlist/quotes`,
    watchlistRecognizeScreenshot: `${API_BASE}/users/watchlist/recognize-screenshot`,
    watchlistBatch: `${API_BASE}/users/watchlist/batch`,
    watchlistGroups: `${API_BASE}/users/watchlist/groups`,
    watchlistGroup: (groupId: number | string) =>
      `${API_BASE}/users/watchlist/groups/${groupId}`,
    watchlistGroupOrder: `${API_BASE}/users/watchlist/groups/order`,
    watchlistItem: (itemId: number | string) =>
      `${API_BASE}/users/watchlist/items/${itemId}`,
  },
  stocks: {
    search: `${API_BASE}/stocks/search`,
    detail: (code: string) => `${API_BASE}/stocks/${code}`,
    quote: (code: string) => `${API_BASE}/stocks/${code}/quote`,
    kline: (code: string) => `${API_BASE}/stocks/${code}/kline`,
    intraday: (code: string) => `${API_BASE}/stocks/${code}/intraday`,
    sectors: (code: string) => `${API_BASE}/stocks/${code}/sectors`,
    aiAnalysis: (code: string) => `${API_BASE}/stocks/${code}/ai-analysis`,
    aiAnalysisDates: (code: string) =>
      `${API_BASE}/stocks/${code}/ai-analysis/dates`,
  },
  kline: {
    get: (code: string) => `${API_BASE}/kline/${code}`,
  },
  chain: {
    industries: `${API_BASE}/chain/industries`,
    alerts: `${API_BASE}/chain/alerts`,
    latest: (industry: string) =>
      `${API_BASE}/chain/${encodeURIComponent(industry)}/latest`,
    versions: (industry: string) =>
      `${API_BASE}/chain/${encodeURIComponent(industry)}/versions`,
    version: (id: number | string) => `${API_BASE}/chain/versions/${id}`,
    compare: `${API_BASE}/chain/versions/compare`,
  },
  research: {
    // 集合端点后端路由为 "/"（带尾斜杠）：不带斜杠会触发 307 重定向
    list: `${API_BASE}/research/`,
    filters: `${API_BASE}/research/filters`,
    detail: (id: number | string) => `${API_BASE}/research/${id}`,
    summarize: (id: number | string) => `${API_BASE}/research/${id}/summarize`,
    pdfUrl: (id: number | string) => `${API_BASE}/research/${id}/pdf-url`,
  },
  skills: {
    list: `${API_BASE}/skills`,
    create: `${API_BASE}/skills`,
    analyze: `${API_BASE}/skills/analyze`,
    detail: (skillId: string) => `${API_BASE}/skills/${skillId}`,
    files: (skillId: string) => `${API_BASE}/skills/${skillId}/files`,
    update: (skillId: string) => `${API_BASE}/skills/${skillId}`,
    publish: (skillId: string) => `${API_BASE}/skills/${skillId}/publish`,
    install: (skillId: string) => `${API_BASE}/skills/${skillId}/install`,
    installToggle: (skillId: string) => `${API_BASE}/skills/${skillId}/install`,
    uninstall: (skillId: string) => `${API_BASE}/skills/${skillId}/install`,
  },
  financialReports: {
    list: `${API_BASE}/financial-reports/`,
    detail: (id: number | string) => `${API_BASE}/financial-reports/${id}`,
    summarize: (id: number | string) =>
      `${API_BASE}/financial-reports/${id}/summarize`,
    pdfUrl: (id: number | string) =>
      `${API_BASE}/financial-reports/${id}/pdf-url`,
    collect: `${API_BASE}/financial-reports/collect`,
    collectLog: (logId: number | string) =>
      `${API_BASE}/financial-reports/collect-logs/${logId}`,
  },
  hotspot: {
    list: `${API_BASE}/hotspot/`,
  },
  financial: {
    health: (code: string) => `${API_BASE}/financial/${code}`,
    history: (code: string) => `${API_BASE}/financial/${code}/history`,
  },
  auction: {
    get: (code: string) => `${API_BASE}/auction/${code}`,
    indexTrend: (days = 30, startDate?: string, endDate?: string) => {
      const params = new URLSearchParams({ days: String(days) })
      if (startDate) params.set('start_date', startDate)
      if (endDate) params.set('end_date', endDate)
      return `${API_BASE}/auction/index-trend?${params.toString()}`
    },
  },
  fundFlow: {
    list: `${API_BASE}/fund-flow/`,
    sectorTrend: `${API_BASE}/fund-flow/sector-trend`,
  },
  anomaly: {
    sector: `${API_BASE}/anomaly/sector`,
    stock: `${API_BASE}/anomaly/stock`,
  },
  market: {
    indices: `${API_BASE}/market/indices`,
    indexIntraday: `${API_BASE}/market/indices/intraday`,
    indexKline: `${API_BASE}/market/indices/kline`,
    stats: `${API_BASE}/market/stats`,
    limitUp: `${API_BASE}/market/limit-up`,
    limitUpIntraday: `${API_BASE}/market/limit-up/intraday`,
    limitUpAiReview: `${API_BASE}/market/limit-up/ai-review`,
    sectors: `${API_BASE}/market/sectors`,
    aiReview: `${API_BASE}/market/ai-review`,
    globalIndices: `${API_BASE}/market/global-indices`,
    globalIndexHistory: `${API_BASE}/market/global-index-history`,
    globalIndexKline: `${API_BASE}/market/global-indices/kline`,
    trackedIndexOptions: `${API_BASE}/market/tracked-indexes`,
    fedWatch: `${API_BASE}/market/fed-watch`,
    sectorQuotes: `${API_BASE}/market/sector-quotes`,
    collect: `${API_BASE}/market/collect`,
  },
  calendar: {
    events: `${API_BASE}/calendar/events`,
    upcoming: `${API_BASE}/calendar/events/upcoming`,
  },
  telegraph: {
    list: `${API_BASE}/telegraph`,
  },
  news: {
    channels: `${API_BASE}/news/channels`,
    feed: `${API_BASE}/news/feed`,
    focus: `${API_BASE}/news/focus`,
    stories: `${API_BASE}/news/stories`,
    story: (id: number | string) => `${API_BASE}/news/stories/${id}`,
    storyTrack: (id: number | string) => `${API_BASE}/news/stories/${id}/track`,
    storyStop: (id: number | string) => `${API_BASE}/news/stories/${id}/stop`,
    topics: `${API_BASE}/news/topics`,
    subscriptions: `${API_BASE}/news/subscriptions`,
    subscription: (id: number | string) =>
      `${API_BASE}/news/subscriptions/${id}`,
  },
  workbench: {
    base: `${API_BASE}/workbench`,
    reviewStatus: `${API_BASE}/workbench/review-status`,
  },
  admin: {
    // 集合根路由后端以 "/" 注册，常量保持同形避免依赖 307 重定向
    users: `${API_BASE}/admin/users/`,
    user: (id: number | string) => `${API_BASE}/admin/users/${id}`,
    userResetPassword: (id: number | string) =>
      `${API_BASE}/admin/users/${id}/reset-password`,
    stocks: `${API_BASE}/admin/stocks/`,
    stock: (id: number | string) => `${API_BASE}/admin/stocks/${id}`,
    reports: `${API_BASE}/admin/reports/`,
    reportStorageSummary: `${API_BASE}/admin/reports/storage-summary`,
    reportCleanup: `${API_BASE}/admin/reports/cleanup-old`,
    report: (id: number | string) => `${API_BASE}/admin/reports/${id}`,
    news: `${API_BASE}/admin/news/`,
    newsItem: (id: number | string) => `${API_BASE}/admin/news/${id}`,
    newsBatchDelete: `${API_BASE}/admin/news/batch-delete`,
    telegraph: `${API_BASE}/admin/telegraph/`,
    telegraphItem: (id: number | string) => `${API_BASE}/admin/telegraph/${id}`,
    telegraphBatchDelete: `${API_BASE}/admin/telegraph/batch-delete`,
    tasks: `${API_BASE}/admin/tasks/`,
    task: (id: number | string) => `${API_BASE}/admin/tasks/${id}`,
    taskTrigger: (id: number | string) => `${API_BASE}/admin/tasks/${id}/trigger`,
    taskPause: (id: number | string) => `${API_BASE}/admin/tasks/${id}/pause`,
    taskResume: (id: number | string) => `${API_BASE}/admin/tasks/${id}/resume`,
    llmConfigs: `${API_BASE}/admin/llm-configs`,
    llmConfig: (id: number | string) => `${API_BASE}/admin/llm-configs/${id}`,
    testLLMConfig: (id: number | string) => `${API_BASE}/admin/llm-configs/${id}/test`,
    setDefaultLLMConfig: (id: number | string) =>
      `${API_BASE}/admin/llm-configs/${id}/set-default`,
    proxyConfigs: `${API_BASE}/admin/proxy-configs`,
    proxyConfig: (id: number | string) => `${API_BASE}/admin/proxy-configs/${id}`,
    testProxyConfig: (id: number | string) =>
      `${API_BASE}/admin/proxy-configs/${id}/test`,
    trackedIndexes: `${API_BASE}/admin/tracked-indexes`,
    trackedIndex: (id: number | string) => `${API_BASE}/admin/tracked-indexes/${id}`,
    trackedIndexToggle: (id: number | string) =>
      `${API_BASE}/admin/tracked-indexes/${id}/toggle`,
    collectorChannels: `${API_BASE}/admin/collector/channels`,
    collectorDataTypes: `${API_BASE}/admin/collector/data-types`,
    collectorDataTypeChannels: (dataType: string) =>
      `${API_BASE}/admin/collector/data-types/${dataType}/channels`,
    collectorChannel: (id: number | string) => `${API_BASE}/admin/collector/channels/${id}`,
    collectorTaskChannels: (task: string) => `${API_BASE}/admin/collector/tasks/${task}/channels`,
    collectorTaskCatalog: `${API_BASE}/admin/collector/tasks/catalog`,
    collectorLogs: `${API_BASE}/admin/collector/logs`,
    runCollectorTask: (task: string) => `${API_BASE}/admin/collector/tasks/${task}/run`,
    aiResults: `${API_BASE}/admin/ai-results/`,
    aiResult: (id: number | string) => `${API_BASE}/admin/ai-results/${id}`,
    aiResultSkills: `${API_BASE}/admin/ai-results/skills`,
    mcpServers: `${API_BASE}/admin/mcp/servers`,
    mcpServer: (id: number | string) => `${API_BASE}/admin/mcp/servers/${id}`,
    mcpServerTest: (id: number | string) => `${API_BASE}/admin/mcp/servers/${id}/test`,
    mcpServerTestDraft: `${API_BASE}/admin/mcp/servers/test`,
  },
} as const
