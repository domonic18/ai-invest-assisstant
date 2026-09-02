import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiCalendarEventResponse } from '@ai-invest/shared'

import { apiClient } from './client'

export interface CalendarEventsParams {
  start: string
  end?: string
  categories?: string[]
  limit?: number
}

export async function fetchCalendarEvents(
  params: CalendarEventsParams,
): Promise<ApiCalendarEventResponse[]> {
  const query = new URLSearchParams({ start: params.start })
  if (params.end) query.set('end', params.end)
  if (params.categories?.length) query.set('categories', params.categories.join(','))
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  const response = await apiClient.get<ApiCalendarEventResponse[]>(
    `${ENDPOINTS.calendar.events}?${query.toString()}`,
  )
  return response.data
}

export async function fetchUpcomingCalendarEvents(
  limit = 10,
): Promise<ApiCalendarEventResponse[]> {
  const response = await apiClient.get<ApiCalendarEventResponse[]>(
    `${ENDPOINTS.calendar.upcoming}?limit=${limit}`,
  )
  return response.data
}
