import { ENDPOINTS } from '@ai-invest/shared'
import type {
  ApiFocusResponse,
  ApiNewsChannelsResponse,
  ApiStorylineDetail,
  ApiSubscription,
  ApiTopicsResponse,
} from '@ai-invest/shared'

import { apiClient } from './client'

/** 渠道监控卡 + 今日统计（wire 与领域同构，直接透传 shared 类型）。 */
export async function fetchNewsChannels(): Promise<ApiNewsChannelsResponse> {
  const response = await apiClient.get<ApiNewsChannelsResponse>(
    ENDPOINTS.news.channels,
  )
  return response.data
}

/** 重点与跟踪视图：今日重点（含评分构成）+ 跟踪中故事线。 */
export async function fetchNewsFocus(): Promise<ApiFocusResponse> {
  const response = await apiClient.get<ApiFocusResponse>(ENDPOINTS.news.focus)
  return response.data
}

/** 当日热点主题快照（session=intraday|post，默认 post）。 */
export async function fetchNewsTopics(
  sessionKey: 'intraday' | 'post' = 'post',
): Promise<ApiTopicsResponse> {
  const response = await apiClient.get<ApiTopicsResponse>(
    ENDPOINTS.news.topics,
    { params: { session: sessionKey } },
  )
  return response.data
}

/** 故事线详情（线卡 + 节点链 + 线内条目回显）。 */
export async function fetchNewsStory(id: number): Promise<ApiStorylineDetail> {
  const response = await apiClient.get<ApiStorylineDetail>(
    ENDPOINTS.news.story(id),
  )
  return response.data
}

/** 以单条资讯手动建线（origin=manual，仅本人视图）。 */
export async function createNewsStory(payload: {
  source: string
  itemId: string
}): Promise<ApiStorylineDetail> {
  const response = await apiClient.post<ApiStorylineDetail>(
    ENDPOINTS.news.stories,
    payload,
  )
  return response.data
}

/** 加入跟踪。 */
export async function trackNewsStory(id: number): Promise<void> {
  await apiClient.post(ENDPOINTS.news.storyTrack(id))
}

/** 停止跟踪（本人视图移除，AI 续接全局进行）。 */
export async function stopNewsStory(id: number): Promise<void> {
  await apiClient.post(ENDPOINTS.news.storyStop(id))
}

/** 我的订阅列表（含命中统计）。 */
export async function fetchNewsSubscriptions(): Promise<ApiSubscription[]> {
  const response = await apiClient.get<ApiSubscription[]>(
    ENDPOINTS.news.subscriptions,
  )
  return response.data
}

/** 新增关键词订阅。 */
export async function createNewsSubscription(payload: {
  keyword: string
  channels?: string[] | null
}): Promise<ApiSubscription> {
  const response = await apiClient.post<ApiSubscription>(
    ENDPOINTS.news.subscriptions,
    payload,
  )
  return response.data
}

/** 更新订阅（渠道 / 推送开关 / 启停）。 */
export async function updateNewsSubscription(
  id: number,
  payload: { channels?: string[] | null; pushEnabled?: boolean; enabled?: boolean },
): Promise<ApiSubscription> {
  const response = await apiClient.patch<ApiSubscription>(
    ENDPOINTS.news.subscription(id),
    payload,
  )
  return response.data
}

/** 删除订阅（级联删命中记录）。 */
export async function deleteNewsSubscription(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.news.subscription(id))
}
