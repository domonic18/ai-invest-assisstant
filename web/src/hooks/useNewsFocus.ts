import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createNewsStory,
  fetchNewsFocus,
  fetchNewsStory,
  stopNewsStory,
  trackNewsStory,
} from '@/api/news'

import { queryKeys } from './queryKeys'

/** 重点与跟踪视图（今日重点 + 跟踪线列表）。 */
export function useNewsFocus() {
  return useQuery({
    queryKey: queryKeys.news.focus,
    queryFn: fetchNewsFocus,
  })
}

/** 故事线详情（线内条目 + 节点链）。 */
export function useNewsStory(id: number | null) {
  return useQuery({
    queryKey: queryKeys.news.story(id ?? 0),
    queryFn: () => fetchNewsStory(id as number),
    enabled: id !== null,
  })
}

/** 线操作（track/stop/create）后失效 focus 与详情缓存。 */
function useInvalidateStories() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.news.focus })
    queryClient.invalidateQueries({ queryKey: ['news', 'story'] })
  }
}

export function useTrackNewsStory() {
  const invalidate = useInvalidateStories()
  return useMutation({
    mutationFn: (id: number) => trackNewsStory(id),
    onSuccess: invalidate,
  })
}

export function useStopNewsStory() {
  const invalidate = useInvalidateStories()
  return useMutation({
    mutationFn: (id: number) => stopNewsStory(id),
    onSuccess: invalidate,
  })
}

export function useCreateNewsStory() {
  const invalidate = useInvalidateStories()
  return useMutation({
    mutationFn: (payload: { source: string; itemId: string }) =>
      createNewsStory(payload),
    onSuccess: invalidate,
  })
}
