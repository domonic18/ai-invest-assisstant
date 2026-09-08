import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiReviewStatus,
  ApiWorkbenchResponse,
  ReviewStatus,
  WorkbenchOverview,
} from '@ai-invest/shared'

import { apiClient } from './client'
import { mapReviewStatus, mapWorkbench } from './mappers/workbench'

export async function fetchWorkbench(): Promise<WorkbenchOverview> {
  const response = await apiClient.get<ApiWorkbenchResponse>(
    ENDPOINTS.workbench.base,
  )
  return mapWorkbench(response.data)
}

/** 复盘引擎状态单查（侧边栏复盘状态块）。 */
export async function fetchReviewStatus(): Promise<ReviewStatus> {
  const response = await apiClient.get<ApiReviewStatus>(
    ENDPOINTS.workbench.reviewStatus,
  )
  return mapReviewStatus(response.data)
}
