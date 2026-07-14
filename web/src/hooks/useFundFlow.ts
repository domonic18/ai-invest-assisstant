import { useQuery } from '@tanstack/react-query'

import { fetchFundFlow, type FundFlowParams } from '@/api/fundFlow'

export function useFundFlow(params: FundFlowParams = {}) {
  return useQuery({
    queryKey: ['fund-flow', params],
    queryFn: () => fetchFundFlow(params),
  })
}
