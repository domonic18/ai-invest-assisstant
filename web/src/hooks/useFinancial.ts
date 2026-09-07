import { useQuery } from '@tanstack/react-query'

import { fetchFinancialHealth } from '@/api/financial'

import { queryKeys } from '@/hooks/queryKeys'

const FINANCIAL_KEY = queryKeys.financial.all

export function useFinancial(code: string, reportDate?: string) {
  return useQuery({
    queryKey: [...FINANCIAL_KEY, code, reportDate],
    queryFn: () => fetchFinancialHealth(code, reportDate),
    enabled: !!code,
  })
}
