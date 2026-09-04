import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiChainAlert,
  ApiChainAnalyzeResponse,
  ApiChainCompareResult,
  ApiChainVersionDetail,
  ApiChainVersionSummary,
  ChainAlert,
  ChainCompareResult,
  ChainVersionDetail,
  ChainVersionSummary,
} from '@ai-invest/shared'

import { apiClient } from './client'
import {
  mapChainAlert,
  mapChainAnalysisResult,
  mapChainCompareResult,
  mapChainVersionDetail,
  mapChainVersionSummary,
} from './mappers'

import type { ChainAnalysisResult } from '@ai-invest/shared'

export interface AnalyzeChainParams {
  industry: string
  focus?: string
}

export interface AnalyzeChainResponse {
  versionId: number
  versionNo: number
  status: string
  result: ChainAnalysisResult | null
}

export async function analyzeChain(
  params: AnalyzeChainParams
): Promise<AnalyzeChainResponse> {
  const response = await apiClient.post<ApiChainAnalyzeResponse>(
    ENDPOINTS.chain.analyze,
    {
      industry: params.industry,
      focus: params.focus,
    }
  )
  return {
    versionId: response.data.versionId,
    versionNo: response.data.versionNo,
    status: response.data.status,
    result: response.data.result
      ? mapChainAnalysisResult(response.data.result)
      : null,
  }
}

export async function fetchChainIndustries(): Promise<string[]> {
  const response = await apiClient.get<string[]>(ENDPOINTS.chain.industries)
  return response.data
}

export async function fetchChainLatest(
  industry: string
): Promise<ChainVersionDetail> {
  const response = await apiClient.get<ApiChainVersionDetail>(
    ENDPOINTS.chain.latest(industry)
  )
  return mapChainVersionDetail(response.data)
}

export async function fetchChainAlerts(
  industry: string,
  days = 30
): Promise<ChainAlert[]> {
  const response = await apiClient.get<ApiChainAlert[]>(
    ENDPOINTS.chain.alerts(industry, days)
  )
  return response.data.map(mapChainAlert)
}

export async function fetchChainVersions(
  industry: string
): Promise<ChainVersionSummary[]> {
  const response = await apiClient.get<ApiChainVersionSummary[]>(
    ENDPOINTS.chain.versions(industry)
  )
  return response.data.map(mapChainVersionSummary)
}

export async function fetchChainVersion(
  versionId: number
): Promise<ChainVersionDetail> {
  const response = await apiClient.get<ApiChainVersionDetail>(
    ENDPOINTS.chain.version(versionId)
  )
  return mapChainVersionDetail(response.data)
}

export async function fetchChainCompare(
  baseId: number,
  targetId: number
): Promise<ChainCompareResult> {
  const response = await apiClient.get<ApiChainCompareResult>(
    ENDPOINTS.chain.compare(baseId, targetId)
  )
  return mapChainCompareResult(response.data)
}
