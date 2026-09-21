import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiKbConsumerSource,
  ApiKbImageUrl,
  ApiKbPlaybackToken,
  ApiKbPublishedChaptersResponse,
  ApiKbSearchResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

/** 消费侧知识库列表（启用中最小投影；403 即未授权）。 */
export async function fetchKbConsumerSources(): Promise<ApiKbConsumerSource[]> {
  const response = await apiClient.get<ApiKbConsumerSource[]>(ENDPOINTS.kb.sources)
  return response.data
}

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

/** 一次性播放凭证（≤30min 绑定用户+素材；携带上/下一集 id）。 */
export async function fetchKbPlaybackToken(mediaId: number): Promise<ApiKbPlaybackToken> {
  const response = await apiClient.post<ApiKbPlaybackToken>(
    ENDPOINTS.kb.playbackToken(mediaId)
  )
  return response.data
}

/** 字幕轨（WebVTT 文本；经 apiClient 同源鉴权，仅 `<video>` src 用 query token）。 */
export async function fetchKbSubtitles(mediaId: number): Promise<string> {
  const response = await apiClient.get<string>(ENDPOINTS.kb.subtitles(mediaId), {
    responseType: 'text',
  })
  return response.data
}

/** 视频代理流 URL（element src 无法携带 Authorization 头，凭证走 query token）。 */
export function kbStreamUrl(mediaId: number, token: string): string {
  return ENDPOINTS.kb.stream(mediaId, token)
}

/** 书页位图 URL（同上，token 走 query）。 */
export function kbBookPageUrl(mediaId: number, pageNo: number, token: string): string {
  return ENDPOINTS.kb.bookPage(mediaId, pageNo, token)
}

/** 图片原图短时效预签名（≤15min，点击原图时签发）。 */
export async function fetchKbImageOriginalUrl(
  imageId: number
): Promise<ApiKbImageUrl> {
  const response = await apiClient.get<ApiKbImageUrl>(
    ENDPOINTS.kb.imageOriginalUrl(imageId)
  )
  return response.data
}
