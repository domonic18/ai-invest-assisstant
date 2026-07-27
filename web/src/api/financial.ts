import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiFinancialHealthResponse, ApiFinancialHistoryResponse } from '@ai-invest/shared'

import { apiClient } from './client'
import { mapFinancialHealth, mapFinancialHistory } from './mappers'

export async function fetchFinancialHealth(
  code: string,
  reportDate?: string,
) {
  const response = await apiClient.get<ApiFinancialHealthResponse>(
    ENDPOINTS.financial.health(code),
    {
      params: reportDate ? { report_date: reportDate } : undefined,
    },
  )
  return mapFinancialHealth(response.data)
}

export async function fetchFinancialHistory(
  code: string,
  limit: number = 8,
) {
  const response = await apiClient.get<ApiFinancialHistoryResponse>(
    ENDPOINTS.financial.history(code),
    {
      params: { limit },
    },
  )
  return mapFinancialHistory(response.data)
}
