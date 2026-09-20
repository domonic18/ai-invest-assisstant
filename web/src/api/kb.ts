import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiKbPublishedChaptersResponse,
  ApiKbSearchResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

export interface KbSearchParams {
  q: string
  sourceId?: number | null
  chapterPath?: string[] | null
  pointType?: string | null
  kind?: 'point' | 'segment' | 'image' | null
}

/** 混合检索（消费侧，query 参数跟随 FastAPI 签名 snake_case）。 */
export async function searchKb(params: KbSearchParams): Promise<ApiKbSearchResponse> {
  const response = await apiClient.get<ApiKbSearchResponse>(ENDPOINTS.kb.search, {
    params: {
      q: params.q,
      source_id: params.sourceId ?? undefined,
      chapter_path: params.chapterPath?.length
        ? params.chapterPath.join(',')
        : undefined,
      point_type: params.pointType ?? undefined,
      kind: params.kind ?? undefined,
    },
  })
  return response.data
}

/** 发布态章节树导航。 */
export async function fetchKbPublishedChapters(
  sourceId: number
): Promise<ApiKbPublishedChaptersResponse> {
  const response = await apiClient.get<ApiKbPublishedChaptersResponse>(
    ENDPOINTS.kb.sourceChapters(sourceId)
  )
  return response.data
}
