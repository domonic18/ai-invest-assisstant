import { useQuery } from '@tanstack/react-query'

import { fetchFinancialHistory } from '@/api/financial'

const FINANCIAL_HISTORY_KEY = ['financial-history'] as const

export function useFinancialHistory(code: string, limit: number = 8) {
  return useQuery({
    queryKey: [...FINANCIAL_HISTORY_KEY, code, limit],
    queryFn: () => fetchFinancialHistory(code, limit),
    enabled: !!code,
  })
}
