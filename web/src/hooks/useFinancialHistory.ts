import { useQuery } from '@tanstack/react-query'

import { fetchFinancialHistory } from '@/api/financial'
import { queryKeys } from '@/hooks/queryKeys'

export function useFinancialHistory(code: string, limit: number = 8) {
  return useQuery({
    queryKey: queryKeys.financial.history(code, limit),
    queryFn: () => fetchFinancialHistory(code, limit),
    enabled: !!code,
  })
}
