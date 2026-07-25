export const API_BASE = '/api/v1'

export const ENDPOINTS = {
  auth: {
    register: `${API_BASE}/auth/register`,
    login: `${API_BASE}/auth/login`,
    wxLogin: `${API_BASE}/auth/wx-login`,
  },
  users: {
    me: `${API_BASE}/users/me`,
    meSettings: `${API_BASE}/users/me/settings`,
    watchlist: `${API_BASE}/users/watchlist`,
    watchlistQuotes: `${API_BASE}/users/watchlist/quotes`,
  },
  stocks: {
    search: `${API_BASE}/stocks/search`,
    detail: (code: string) => `${API_BASE}/stocks/${code}`,
  },
  kline: {
    get: (code: string) => `${API_BASE}/kline/${code}`,
  },
  chain: {
    analyze: `${API_BASE}/chain/analyze`,
    latest: (industry: string) =>
      `${API_BASE}/chain/${encodeURIComponent(industry)}/latest`,
    versions: (industry: string) =>
      `${API_BASE}/chain/${encodeURIComponent(industry)}/versions`,
    version: (id: number | string) => `${API_BASE}/chain/versions/${id}`,
    compare: (baseId: number, targetId: number) =>
      `${API_BASE}/chain/versions/compare?base_id=${baseId}&target_id=${targetId}`,
  },
  research: {
    list: `${API_BASE}/research`,
    filters: `${API_BASE}/research/filters`,
    detail: (id: number | string) => `${API_BASE}/research/${id}`,
    summarize: (id: number | string) => `${API_BASE}/research/${id}/summarize`,
    pdfUrl: (id: number | string) => `${API_BASE}/research/${id}/pdf-url`,
  },
  financialReports: {
    list: `${API_BASE}/financial-reports`,
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
    list: `${API_BASE}/hotspot`,
  },
  financial: {
    health: (code: string) => `${API_BASE}/financial/${code}`,
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
    list: `${API_BASE}/fund-flow`,
    sectorTrend: (sectorType = 'industry', days = 60) =>
      `${API_BASE}/fund-flow/sector-trend?sector_type=${sectorType}&days=${days}`,
  },
  market: {
    indices: `${API_BASE}/market/indices`,
    indexIntraday: (code: string) => `${API_BASE}/market/indices/intraday?code=${code}`,
    indexKline: (code: string) => `${API_BASE}/market/indices/kline?code=${code}`,
    stats: `${API_BASE}/market/stats`,
    limitUp: `${API_BASE}/market/limit-up`,
    limitUpIntraday: `${API_BASE}/market/limit-up/intraday`,
    limitUpAiReview: `${API_BASE}/market/limit-up/ai-review`,
    sectors: `${API_BASE}/market/sectors`,
    aiReview: `${API_BASE}/market/ai-review`,
    collect: `${API_BASE}/market/collect`,
  },
  admin: {
    users: `${API_BASE}/admin/users`,
    user: (id: number | string) => `${API_BASE}/admin/users/${id}`,
    userResetPassword: (id: number | string) =>
      `${API_BASE}/admin/users/${id}/reset-password`,
    stocks: `${API_BASE}/admin/stocks`,
    stock: (id: number | string) => `${API_BASE}/admin/stocks/${id}`,
    reports: `${API_BASE}/admin/reports`,
    report: (id: number | string) => `${API_BASE}/admin/reports/${id}`,
    news: `${API_BASE}/admin/news`,
    newsItem: (id: number | string) => `${API_BASE}/admin/news/${id}`,
    tasks: `${API_BASE}/admin/tasks`,
    task: (id: number | string) => `${API_BASE}/admin/tasks/${id}`,
    taskTrigger: (id: number | string) => `${API_BASE}/admin/tasks/${id}/trigger`,
    taskPause: (id: number | string) => `${API_BASE}/admin/tasks/${id}/pause`,
    taskResume: (id: number | string) => `${API_BASE}/admin/tasks/${id}/resume`,
    llmConfigs: `${API_BASE}/admin/llm-configs`,
    llmConfig: (id: number | string) => `${API_BASE}/admin/llm-configs/${id}`,
    testLLMConfig: (id: number | string) => `${API_BASE}/admin/llm-configs/${id}/test`,
    setDefaultLLMConfig: (id: number | string) =>
      `${API_BASE}/admin/llm-configs/${id}/set-default`,
    collectorChannels: `${API_BASE}/admin/collector/channels`,
    collectorDataTypes: `${API_BASE}/admin/collector/data-types`,
    collectorDataTypeChannels: (dataType: string) =>
      `${API_BASE}/admin/collector/data-types/${dataType}/channels`,
    collectorChannel: (id: number | string) => `${API_BASE}/admin/collector/channels/${id}`,
    collectorTaskChannels: (task: string) => `${API_BASE}/admin/collector/tasks/${task}/channels`,
    collectorLogs: `${API_BASE}/admin/collector/logs`,
    runCollectorTask: (task: string) => `${API_BASE}/admin/collector/tasks/${task}/run`,
  },
} as const
