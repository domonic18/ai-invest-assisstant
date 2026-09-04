import { useQuery } from '@tanstack/react-query'

import { fetchFinancialHealth } from '@/api/financial'

const FINANCIAL_KEY = ['financial'] as const

export function useFinancial(code: string, reportDate?: string) {
  return useQuery({
    queryKey: [...FINANCIAL_KEY, code, reportDate],
    queryFn: () => fetchFinancialHealth(code, reportDate),
    enabled: !!code,
  })
}
