import { useQuery } from '@tanstack/react-query'

import { fetchFundFlow } from '@/api/fundFlow'

export function useFundFlow(stockCode?: string, limit = 10) {
  return useQuery({
    queryKey: ['fund-flow', stockCode, limit],
    queryFn: () => fetchFundFlow({ stockCode, pageSize: limit }),
  })
}
