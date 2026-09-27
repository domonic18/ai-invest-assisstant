import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiTradeCalendarSeedResult, ApiTradeCalendarYear } from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchTradeCalendarYear(year: number): Promise<ApiTradeCalendarYear> {
  const response = await apiClient.get<ApiTradeCalendarYear>(
    ENDPOINTS.admin.tradeCalendar,
    { params: { year } },
  )
  return response.data
}

export async function updateTradeCalendarDay(
  day: string,
  isTrading: boolean,
  remark?: string | null,
): Promise<void> {
  await apiClient.put(ENDPOINTS.admin.tradeCalendarDay(day), {
    isTrading,
    remark: remark ?? null,
  })
}

export async function seedTradeCalendar(years?: number[]): Promise<ApiTradeCalendarSeedResult> {
  const response = await apiClient.post<ApiTradeCalendarSeedResult>(
    ENDPOINTS.admin.tradeCalendarSeed,
    { years: years ?? null },
  )
  return response.data
}
