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
    meQuota: `${API_BASE}/users/me/quota`,
    meUsage: `${API_BASE}/users/me/usage`,
    meLlmConfig: `${API_BASE}/users/me/llm-config`,
    meLlmConfigTest: `${API_BASE}/users/me/llm-config/test`,
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
  klineDrawings: {
    base: `${API_BASE}/kline-drawings`,
    item: (id: number | string) => `${API_BASE}/kline-drawings/${id}`,
    adopt: `${API_BASE}/kline-drawings/ai/adopt`,
    aiItem: `${API_BASE}/kline-drawings/ai/item`,
    aiClear: `${API_BASE}/kline-drawings/ai/clear`,
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
    sectorDates: `${API_BASE}/anomaly/sector/dates`,
    stock: `${API_BASE}/anomaly/stock`,
    stockDates: `${API_BASE}/anomaly/stock/dates`,
  },
  sectorDetail: {
    get: (sectorType: string, sectorCode: string) =>
      `${API_BASE}/sectors/${sectorType}/${sectorCode}`,
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
    aiReviewDates: `${API_BASE}/market/ai-review/dates`,
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
  social: {
    sentimentFeed: `${API_BASE}/social/sentiment-feed`,
    accounts: `${API_BASE}/social/accounts`,
    accountTimeline: (accountId: number | string) =>
      `${API_BASE}/social/accounts/${accountId}/timeline`,
  },
  screening: {
    query: `${API_BASE}/screening/query`,
  },
  kb: {
    search: `${API_BASE}/kb/search`,
    sources: `${API_BASE}/kb/sources`,
    sourceChapters: (sourceId: number | string) =>
      `${API_BASE}/kb/sources/${sourceId}/chapters`,
    chapterPoints: (sourceId: number | string) =>
      `${API_BASE}/kb/sources/${sourceId}/points`,
    playbackToken: (mediaId: number | string) =>
      `${API_BASE}/kb/media/${mediaId}/playback-token`,
    stream: (mediaId: number | string, token: string) =>
      `${API_BASE}/kb/stream/${mediaId}?token=${encodeURIComponent(token)}`,
    bookPage: (mediaId: number | string, pageNo: number, token: string) =>
      `${API_BASE}/kb/books/${mediaId}/pages/${pageNo}?token=${encodeURIComponent(token)}`,
    subtitles: (mediaId: number | string) =>
      `${API_BASE}/kb/media/${mediaId}/subtitles.vtt`,
    imageOriginalUrl: (imageId: number | string) =>
      `${API_BASE}/kb/images/${imageId}/original-url`,
  },
  admin: {
    // 集合根路由后端以 "/" 注册，常量保持同形避免依赖 307 重定向
    users: `${API_BASE}/admin/users/`,
    user: (id: number | string) => `${API_BASE}/admin/users/${id}`,
    userResetPassword: (id: number | string) =>
      `${API_BASE}/admin/users/${id}/reset-password`,
    usersPending: `${API_BASE}/admin/users/pending`,
    usersPendingCount: `${API_BASE}/admin/users/pending-count`,
    userApprove: (id: number | string) => `${API_BASE}/admin/users/${id}/approve`,
    userReject: (id: number | string) => `${API_BASE}/admin/users/${id}/reject`,
    userQuota: (id: number | string) => `${API_BASE}/admin/users/${id}/quota`,
    usageDashboard: (days = 30) => `${API_BASE}/admin/usage/dashboard?days=${days}`,
    usagePerUsers: (days = 30) => `${API_BASE}/admin/usage/users?days=${days}`,
    accountSettings: `${API_BASE}/admin/settings/account`,
    stocks: `${API_BASE}/admin/stocks/`,
    stock: (id: number | string) => `${API_BASE}/admin/stocks/${id}`,
    reports: `${API_BASE}/admin/reports/`,
    reportStorageSummary: `${API_BASE}/admin/reports/storage-summary`,
    reportCleanup: `${API_BASE}/admin/reports/cleanup-old`,
    report: (id: number | string) => `${API_BASE}/admin/reports/${id}`,
    news: `${API_BASE}/admin/news/`,
    newsItem: (id: number | string) => `${API_BASE}/admin/news/${id}`,
    newsBatchDelete: `${API_BASE}/admin/news/batch-delete`,
    newsFlashDisplay: `${API_BASE}/admin/news/flash-display`,
    telegraph: `${API_BASE}/admin/telegraph/`,
    telegraphItem: (id: number | string) => `${API_BASE}/admin/telegraph/${id}`,
    telegraphBatchDelete: `${API_BASE}/admin/telegraph/batch-delete`,
    tasks: `${API_BASE}/admin/tasks/`,
    task: (id: number | string) => `${API_BASE}/admin/tasks/${id}`,
    taskTrigger: (id: number | string) => `${API_BASE}/admin/tasks/${id}/trigger`,
    taskPause: (id: number | string) => `${API_BASE}/admin/tasks/${id}/pause`,
    taskResume: (id: number | string) => `${API_BASE}/admin/tasks/${id}/resume`,
    llmConfigs: `${API_BASE}/admin/model-configs/llm`,
    llmConfig: (id: number | string) => `${API_BASE}/admin/model-configs/llm/${id}`,
    testLLMConfig: (id: number | string) =>
      `${API_BASE}/admin/model-configs/llm/${id}/test`,
    setDefaultLLMConfig: (id: number | string) =>
      `${API_BASE}/admin/model-configs/llm/${id}/set-default`,
    kbSettings: `${API_BASE}/admin/kb/settings`,
    kbUsage: `${API_BASE}/admin/kb/usage`,
    kbSources: `${API_BASE}/admin/kb/sources`,
    kbSource: (id: number | string) => `${API_BASE}/admin/kb/sources/${id}`,
    kbSourceRestore: (id: number | string) =>
      `${API_BASE}/admin/kb/sources/${id}/restore`,
    kbSourceMedia: (sourceId: number | string) =>
      `${API_BASE}/admin/kb/sources/${sourceId}/media`,
    kbSourceMediaInit: (sourceId: number | string) =>
      `${API_BASE}/admin/kb/sources/${sourceId}/media/init`,
    kbCostEstimate: `${API_BASE}/admin/kb/cost-estimate`,
    kbSourceConfirmCost: (sourceId: number | string) =>
      `${API_BASE}/admin/kb/sources/${sourceId}/confirm-cost`,
    kbMedia: (id: number | string) => `${API_BASE}/admin/kb/media/${id}`,
    kbMediaUploadSession: (id: number | string) =>
      `${API_BASE}/admin/kb/media/${id}/upload-session`,
    kbMediaUploaded: (id: number | string) =>
      `${API_BASE}/admin/kb/media/${id}/uploaded`,
    kbMediaRequeue: (id: number | string) =>
      `${API_BASE}/admin/kb/media/${id}/requeue`,
    kbMediaRestore: (id: number | string) =>
      `${API_BASE}/admin/kb/media/${id}/restore`,
    kbSourceTranscript: (sourceId: number | string, mediaId: number | string) =>
      `${API_BASE}/admin/kb/sources/${sourceId}/transcript/${mediaId}`,
    kbSourceChapters: (sourceId: number | string) =>
      `${API_BASE}/admin/kb/sources/${sourceId}/chapters`,
    kbSourceChaptersPublish: (sourceId: number | string) =>
      `${API_BASE}/admin/kb/sources/${sourceId}/chapters/publish`,
    kbSourcePoints: (sourceId: number | string) =>
      `${API_BASE}/admin/kb/sources/${sourceId}/points`,
    kbSourceImages: (sourceId: number | string) =>
      `${API_BASE}/admin/kb/sources/${sourceId}/images`,
    kbImage: (id: number | string) => `${API_BASE}/admin/kb/images/${id}`,
    kbImageRedescribe: (id: number | string) =>
      `${API_BASE}/admin/kb/images/${id}/redescribe`,
    kbPoints: `${API_BASE}/admin/kb/points`,
    kbPoint: (id: number | string) => `${API_BASE}/admin/kb/points/${id}`,
    kbPointApprove: (id: number | string) =>
      `${API_BASE}/admin/kb/points/${id}/approve`,
    kbPointReject: (id: number | string) =>
      `${API_BASE}/admin/kb/points/${id}/reject`,
    kbPointsMerge: `${API_BASE}/admin/kb/points/merge`,
    kbPointsApproveBatch: `${API_BASE}/admin/kb/points/approve-batch`,
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
    collectorChannelDebug: (id: number | string) =>
      `${API_BASE}/admin/collector/channels/${id}/debug`,
    collectorTaskChannels: (task: string) => `${API_BASE}/admin/collector/tasks/${task}/channels`,
    collectorTaskCatalog: `${API_BASE}/admin/collector/tasks/catalog`,
    collectorLogs: `${API_BASE}/admin/collector/logs`,
    collectorLogSummary: `${API_BASE}/admin/collector/logs/summary`,
    runCollectorTask: (task: string) => `${API_BASE}/admin/collector/tasks/${task}/run`,
    collectorHealthOverview: `${API_BASE}/admin/collector/health/overview`,
    collectorHealthTasks: `${API_BASE}/admin/collector/health/tasks`,
    collectorHealthChannels: `${API_BASE}/admin/collector/health/channels`,
    collectorHealthScheduleCheck: `${API_BASE}/admin/collector/health/schedule-check`,
    collectorHealthRun: `${API_BASE}/admin/collector/health/run`,
    collectorHealthSnapshots: `${API_BASE}/admin/collector/health/snapshots`,
    aiResults: `${API_BASE}/admin/ai-results/`,
    aiResult: (id: number | string) => `${API_BASE}/admin/ai-results/${id}`,
    aiResultSkills: `${API_BASE}/admin/ai-results/skills`,
    mcpServers: `${API_BASE}/admin/mcp/servers`,
    mcpServer: (id: number | string) => `${API_BASE}/admin/mcp/servers/${id}`,
    mcpServerTest: (id: number | string) => `${API_BASE}/admin/mcp/servers/${id}/test`,
    mcpServerTestDraft: `${API_BASE}/admin/mcp/servers/test`,
    systemStatus: `${API_BASE}/admin/system/status`,
    socialAccounts: `${API_BASE}/admin/social/accounts`,
    socialAccount: (id: number | string) => `${API_BASE}/admin/social/accounts/${id}`,
    socialAccountBackfill: (id: number | string) =>
      `${API_BASE}/admin/social/accounts/${id}/backfill`,
    socialAccountPosts: (id: number | string) =>
      `${API_BASE}/admin/social/accounts/${id}/posts`,
    socialStatus: `${API_BASE}/admin/social/status`,
    socialCookies: `${API_BASE}/admin/social/cookies`,
    asrConfig: `${API_BASE}/admin/model-configs/asr`,
    asrConfigTest: `${API_BASE}/admin/model-configs/asr/test`,
  },
} as const
