import { useQuery } from '@tanstack/react-query'

import { fetchNewsTopics } from '@/api/news'

import { queryKeys } from './queryKeys'

/** 当日热点主题快照（session=intraday|post）。 */
export function useNewsTopics(sessionKey: 'intraday' | 'post') {
  return useQuery({
    queryKey: queryKeys.news.topics(sessionKey),
    queryFn: () => fetchNewsTopics(sessionKey),
  })
}
