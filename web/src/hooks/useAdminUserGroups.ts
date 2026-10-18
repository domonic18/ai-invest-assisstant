import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type {
  ApiUserGroupCreateRequest,
  ApiUserGroupUpdateRequest,
} from '@ai-invest/shared'

import {
  createAdminUserGroup,
  deleteAdminUserGroup,
  fetchAdminUserGroups,
  updateAdminUserGroup,
} from '@/api/adminUserGroups'
import { queryKeys } from '@/hooks/queryKeys'

// 组变更同时影响用户列表的 groupName 展示与登录用户的权限集
const GROUPS_KEY = queryKeys.admin.userGroups

export function useAdminUserGroups() {
  return useQuery({
    queryKey: GROUPS_KEY,
    queryFn: fetchAdminUserGroups,
  })
}

export function useCreateAdminUserGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiUserGroupCreateRequest) => createAdminUserGroup(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GROUPS_KEY })
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users })
    },
  })
}

export function useUpdateAdminUserGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiUserGroupUpdateRequest }) =>
      updateAdminUserGroup(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GROUPS_KEY })
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users })
    },
  })
}

export function useDeleteAdminUserGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteAdminUserGroup(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: GROUPS_KEY })
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users })
    },
  })
}
