import { ENDPOINTS } from '@ai-invest/shared'
import type { ApiWorkbenchResponse, WorkbenchOverview } from '@ai-invest/shared'

import { apiClient } from './client'
import { mapWorkbench } from './mappers/workbench'

export async function fetchWorkbench(): Promise<WorkbenchOverview> {
  const response = await apiClient.get<ApiWorkbenchResponse>(
    ENDPOINTS.workbench.base,
  )
  return mapWorkbench(response.data)
}
