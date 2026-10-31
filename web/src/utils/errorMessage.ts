import axios from 'axios'

/** HTTP 状态码（非 axios 错误或无响应时 undefined）。 */
export function apiErrorStatus(err: unknown): number | undefined {
  return axios.isAxiosError(err) ? err.response?.status : undefined
}

export function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    if (typeof detail === 'string' && detail) return detail
  }
  return fallback
}
