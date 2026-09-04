import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiDataTypeChannelPriorityInput,
  ApiDataTypeChannelsResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

export async function fetchCollectorDataTypes(): Promise<ApiDataTypeChannelsResponse[]> {
  const { data } = await apiClient.get<ApiDataTypeChannelsResponse[]>(
    ENDPOINTS.admin.collectorDataTypes,
  )
  return data
}

export async function replaceDataTypeChannels(
  dataType: string,
  items: ApiDataTypeChannelPriorityInput[],
): Promise<ApiDataTypeChannelsResponse> {
  const { data } = await apiClient.put<ApiDataTypeChannelsResponse>(
    ENDPOINTS.admin.collectorDataTypeChannels(dataType),
    items,
  )
  return data
}
