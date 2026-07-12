export const API_BASE = '/api/v1'

export const ENDPOINTS = {
  auth: {
    register: `${API_BASE}/auth/register`,
    login: `${API_BASE}/auth/login`,
    wxLogin: `${API_BASE}/auth/wx-login`,
  },
  users: {
    me: `${API_BASE}/users/me`,
    watchlist: `${API_BASE}/users/watchlist`,
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
  },
  research: {
    list: `${API_BASE}/research`,
    detail: (id: string) => `${API_BASE}/research/${id}`,
    summarize: (id: string) => `${API_BASE}/research/${id}/summarize`,
  },
  hotspot: {
    list: `${API_BASE}/hotspot`,
  },
  financial: {
    health: (code: string) => `${API_BASE}/financial/${code}`,
  },
  auction: {
    get: (code: string) => `${API_BASE}/auction/${code}`,
  },
  fundFlow: {
    list: `${API_BASE}/fund-flow`,
  },
} as const
