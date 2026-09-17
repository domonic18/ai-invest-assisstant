/** 社媒大 V 情绪查询 hooks（情绪流/账号卡/单账号时间线）。 */

import { keepPreviousData, useQuery } from '@tanstack/react-query'

import type { ApiSocialStance } from '@ai-invest/shared'

import { fetchSentimentFeed, fetchSocialAccountCards, fetchSocialTimeline } from '@/api/social'
import type { SentimentFeedParams } from '@/api/social'
import { queryKeys } from '@/hooks/queryKeys'

/** 情绪流刷新间隔：判断任务 10 分钟一轮，60s 轮询足够跟上节拍。 */
export const SENTIMENT_REFETCH_INTERVAL = 60_000

/** feed 过滤器（TanStack key 序列化用）。 */
export interface SentimentFilters {
  category?: string
  stance?: ApiSocialStance
  hours?: number
  strongOnly?: boolean
}

export function filterKey(filters: SentimentFilters): string {
  return JSON.stringify([
    filters.category ?? null,
    filters.stance ?? null,
    filters.hours ?? null,
    filters.strongOnly ?? false,
  ])
}

export function useSentimentFeed(
  page: number,
  pageSize: number,
  filters: SentimentFilters = {},
  autoRefresh = true,
) {
  return useQuery({
    queryKey: queryKeys.social.feed(page, pageSize, filterKey(filters)),
    queryFn: () =>
      fetchSentimentFeed({ ...filters, page, pageSize } satisfies SentimentFeedParams),
    placeholderData: keepPreviousData,
    refetchInterval: autoRefresh ? SENTIMENT_REFETCH_INTERVAL : false,
  })
}

export function useSocialAccountCards() {
  return useQuery({
    queryKey: queryKeys.social.accounts,
    queryFn: fetchSocialAccountCards,
  })
}

export function useSocialTimeline(
  accountId: number | null,
  page: number,
  pageSize: number,
) {
  return useQuery({
    queryKey: queryKeys.social.timeline(accountId ?? 0, page, pageSize),
    queryFn: () => fetchSocialTimeline(accountId as number, { page, pageSize }),
    enabled: accountId !== null,
    placeholderData: keepPreviousData,
  })
}
