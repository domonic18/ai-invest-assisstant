import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createTrackedIndex,
  deleteTrackedIndex,
  fetchTrackedIndexes,
  toggleTrackedIndex,
  updateTrackedIndex,
} from '@/api/trackedIndex'
import { mapTrackedIndex } from '@/api/mappers'
import { queryKeys } from '@/hooks/queryKeys'
import type {
  ApiTrackedIndexCreateRequest,
  ApiTrackedIndexUpdateRequest,
} from '@ai-invest/shared'

const KEY = queryKeys.trackedIndexes

export function useTrackedIndexes() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const data = await fetchTrackedIndexes()
      return data.map(mapTrackedIndex)
    },
  })
}

export function useCreateTrackedIndex() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiTrackedIndexCreateRequest) => createTrackedIndex(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateTrackedIndex() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiTrackedIndexUpdateRequest }) =>
      updateTrackedIndex(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useDeleteTrackedIndex() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteTrackedIndex(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useToggleTrackedIndex() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => toggleTrackedIndex(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}
