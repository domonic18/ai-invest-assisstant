import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createAdminUser,
  deleteAdminUser,
  fetchAdminUsers,
  resetAdminUserPassword,
  updateAdminUser,
  type AdminUserParams,
} from '@/api/adminUsers'
import type {
  ApiAdminUserCreateRequest,
  ApiAdminUserResetPasswordRequest,
  ApiAdminUserUpdateRequest,
} from '@ai-invest/shared'

const ADMIN_USERS_KEY = ['admin-users'] as const

export function useAdminUsers(params: AdminUserParams = {}) {
  return useQuery({
    queryKey: [...ADMIN_USERS_KEY, params],
    queryFn: () => fetchAdminUsers(params),
  })
}

export function useCreateAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAdminUserCreateRequest) => createAdminUser(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY }),
  })
}

export function useUpdateAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiAdminUserUpdateRequest }) => updateAdminUser(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY }),
  })
}

export function useDeleteAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAdminUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ADMIN_USERS_KEY }),
  })
}

export function useResetAdminUserPassword() {
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiAdminUserResetPasswordRequest }) => resetAdminUserPassword(id, data),
  })
}
