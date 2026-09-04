import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createAdminTask,
  deleteAdminTask,
  fetchAdminTasks,
  pauseAdminTask,
  resumeAdminTask,
  triggerAdminTask,
  updateAdminTask,
  type AdminTaskParams,
} from '@/api/adminTasks'
import type {
  ApiAdminTaskCreateRequest,
  ApiAdminTaskUpdateRequest,
} from '@ai-invest/shared'

const ADMIN_TASKS_KEY = ['admin-tasks'] as const

export function useAdminTasks(params: AdminTaskParams = {}) {
  return useQuery({
    queryKey: [...ADMIN_TASKS_KEY, params],
    queryFn: () => fetchAdminTasks(params),
  })
}

export function useCreateAdminTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAdminTaskCreateRequest) => createAdminTask(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_TASKS_KEY }),
  })
}

export function useUpdateAdminTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiAdminTaskUpdateRequest }) => updateAdminTask(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_TASKS_KEY }),
  })
}

export function useDeleteAdminTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAdminTask(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_TASKS_KEY }),
  })
}

export function usePauseAdminTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => pauseAdminTask(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_TASKS_KEY }),
  })
}

export function useResumeAdminTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => resumeAdminTask(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_TASKS_KEY }),
  })
}

export function useTriggerAdminTask() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => triggerAdminTask(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_TASKS_KEY }),
  })
}
