import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiSectorFlowTrendResponse } from '@ai-invest/shared'

import { apiClient } from './client'

export type SectorType = 'industry' | 'concept'
export type SectorFlowTrend = ApiSectorFlowTrendResponse

export async function fetchSectorFundFlowTrend(
  sectorType: SectorType = 'industry',
  days = 60,
): Promise<SectorFlowTrend> {
  const response = await apiClient.get<ApiSectorFlowTrendResponse>(
    ENDPOINTS.fundFlow.sectorTrend(sectorType, days),
  )
  return response.data
}
