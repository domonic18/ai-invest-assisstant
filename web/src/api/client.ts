import axios from 'axios'

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

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
