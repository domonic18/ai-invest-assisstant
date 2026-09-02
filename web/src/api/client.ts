import axios from 'axios'

declare module 'axios' {
  export interface AxiosRequestConfig {
    /** GET 幂等重试标记（502/503/504/网络错误），防拦截器死循环 */
    __retried?: number
  }
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // 全局清理 query params：空字符串 / null / undefined 一律不发
  // 避免 FastAPI 把 `?trade_date=` 当作 date 类型解析失败返回 422
  if (config.params != null && typeof config.params === 'object') {
    const cleaned: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(config.params)) {
      if (value === '' || value == null) continue
      cleaned[key] = value
    }
    config.params = cleaned
  }
  return config
})

const RETRYABLE_STATUS = new Set([502, 503, 504])
const MAX_RETRIES = 2

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error as {
      config?: import('axios').InternalAxiosRequestConfig
      response?: { status: number; data?: { detail?: unknown } }
    }

    // 冷启动/网关瞬时故障：仅幂等 GET 自动重试（1s / 2s 退避）
    const retryable =
      config &&
      (config.method ?? 'get').toLowerCase() === 'get' &&
      (!response || RETRYABLE_STATUS.has(response.status))
    if (retryable && (config.__retried ?? 0) < MAX_RETRIES) {
      config.__retried = (config.__retried ?? 0) + 1
      await sleep(1000 * config.__retried)
      return apiClient.request(config)
    }

    if (response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    // 服务端 detail 转为 message 展示；原地改写保留 response/status 供调用方判断
    const serverDetail = response?.data?.detail
    if (serverDetail && error instanceof Error) {
      error.message =
        typeof serverDetail === 'string' ? serverDetail : JSON.stringify(serverDetail)
    }
    return Promise.reject(error)
  }
)
