import { useQuery } from '@tanstack/react-query'

import { fetchKbPublishedChapters, searchKb } from '@/api/kb'
import { queryKeys } from '@/hooks/queryKeys'

/** 混合检索（submitted 为 null 时不发起，作为受控触发器）。 */
export function useKbSearch(
  submitted: { q: string; sourceId: number | null; chapterPath: string[]; kind: string | null } | null
) {
  return useQuery({
    queryKey: submitted
      ? queryKeys.kb.search(submitted.q, submitted.sourceId, submitted.chapterPath, submitted.kind)
      : ['kb', 'search', 'idle'],
    queryFn: () =>
      searchKb({
        q: submitted!.q,
        sourceId: submitted!.sourceId,
        chapterPath: submitted!.chapterPath.length ? submitted!.chapterPath : null,
        kind: (submitted!.kind as 'point' | 'segment' | 'image' | null) ?? null,
      }),
    enabled: submitted !== null,
    staleTime: 30_000,
  })
}

/** 发布态章节树导航。 */
export function useKbPublishedChapters(sourceId: number | null) {
  return useQuery({
    queryKey: queryKeys.kb.chaptersPublished(sourceId ?? 0),
    queryFn: () => fetchKbPublishedChapters(sourceId!),
    enabled: sourceId !== null,
    staleTime: 5 * 60_000,
  })
}
