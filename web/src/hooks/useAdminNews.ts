import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createAdminNews,
  deleteAdminNews,
  fetchAdminNews,
  updateAdminNews,
  type AdminNewsParams,
} from '@/api/adminNews'
import type {
  ApiAdminNewsCreateRequest,
  ApiAdminNewsUpdateRequest,
} from '@ai-invest/shared'

const ADMIN_NEWS_KEY = ['admin-news'] as const

export function useAdminNews(params: AdminNewsParams = {}) {
  return useQuery({
    queryKey: [...ADMIN_NEWS_KEY, params],
    queryFn: () => fetchAdminNews(params),
  })
}

export function useCreateAdminNews() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAdminNewsCreateRequest) => createAdminNews(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_NEWS_KEY }),
  })
}

export function useUpdateAdminNews() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiAdminNewsUpdateRequest }) => updateAdminNews(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_NEWS_KEY }),
  })
}

export function useDeleteAdminNews() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAdminNews(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_NEWS_KEY }),
  })
}
