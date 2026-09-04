import { useQuery } from '@tanstack/react-query'

import { fetchCalendarEvents } from '@/api/calendar'
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
