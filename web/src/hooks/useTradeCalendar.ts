import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  fetchTradeCalendarYear,
  seedTradeCalendar,
  updateTradeCalendarDay,
} from '@/api/adminTradeCalendar'

import { queryKeys } from './queryKeys'

export function useTradeCalendarYear(year: number) {
  return useQuery({
    queryKey: queryKeys.tradeCalendar.year(year),
    queryFn: () => fetchTradeCalendarYear(year),
    staleTime: 60 * 1000,
  })
}

export function useToggleTradeCalendarDay(year: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ day, isTrading, remark }: { day: string; isTrading: boolean; remark?: string | null }) =>
      updateTradeCalendarDay(day, isTrading, remark),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tradeCalendar.year(year) })
    },
  })
}

export function useSeedTradeCalendar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (years?: number[]) => seedTradeCalendar(years),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trade-calendar'] })
    },
  })
}
