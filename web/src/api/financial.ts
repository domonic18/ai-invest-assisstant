import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiFinancialHealthResponse } from '@ai-invest/shared'

import { apiClient } from './client'
import { mapFinancialHealth } from './mappers'

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
