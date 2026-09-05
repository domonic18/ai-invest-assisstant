import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiChainAlert,
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
  mapChainCompareResult,
  mapChainVersionDetail,
  mapChainVersionSummary,
} from './mappers'

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

export async function deleteChainVersion(versionId: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.chain.version(versionId))
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
