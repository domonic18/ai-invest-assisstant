import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiChainAnalysisResult } from '@ai-invest/shared'

import { apiClient } from './client'
import { mapChainAnalysisResult } from './mappers'

export interface AnalyzeChainParams {
  industry: string
  focus?: string
}

export async function analyzeChain(params: AnalyzeChainParams) {
  const response = await apiClient.post<ApiChainAnalysisResult>(ENDPOINTS.chain.analyze, {
    industry: params.industry,
    focus: params.focus,
  })
  return mapChainAnalysisResult(response.data)
}
