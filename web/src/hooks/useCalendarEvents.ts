import { useQuery } from '@tanstack/react-query'

import { fetchCalendarEvents, fetchUpcomingCalendarEvents } from '@/api/calendar'
import { mapCalendarEvent } from '@/api/mappers'
import { queryKeys } from '@/hooks/queryKeys'

/** 查询 [start, end] 北京日历日区间内的日历事件（start/end 为 YYYY-MM-DD）。 */
export function useCalendarEvents(start: string, end: string) {
  return useQuery({
    queryKey: queryKeys.calendar.events(start, end),
    queryFn: async () => {
      const data = await fetchCalendarEvents({ start, end })
      return data.map(mapCalendarEvent)
    },
  })
}

/** 未来 N 条日历事件（宏观页日程卡：FOMC/CPI 高亮）。 */
export function useUpcomingCalendarEvents(limit = 10) {
  return useQuery({
    queryKey: queryKeys.calendar.upcoming(limit),
    queryFn: async () => {
      const data = await fetchUpcomingCalendarEvents(limit)
      return data.map(mapCalendarEvent)
    },
    staleTime: 5 * 60_000,
  })
}
