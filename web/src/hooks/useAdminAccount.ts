import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  ApiAccountSettingsUpdateRequest,
  ApiApproveRequest,
  ApiQuotaAdjustRequest,
  ApiRejectRequest,
} from '@ai-invest/shared'

import {
  adjustUserQuota,
  approveUser,
  fetchAccountSettings,
  fetchPendingApplications,
  fetchPendingCount,
  fetchUsageDashboard,
  fetchUsagePerUsers,
  rejectUser,
  updateAccountSettings,
} from '@/api/adminAccount'
import { queryKeys } from '@/hooks/queryKeys'

/** 待审角标：仅 admin 启用（配合 Sidebar 轮询） */
export function usePendingCount(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.admin.pendingCount,
    queryFn: fetchPendingCount,
    enabled,
    refetchInterval: 300_000,
  })
}

export function usePendingApplications() {
  return useQuery({
    queryKey: queryKeys.admin.pendingApplications,
    queryFn: fetchPendingApplications,
  })
}

function useInvalidateUsers() {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.users })
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.pendingApplications })
    queryClient.invalidateQueries({ queryKey: queryKeys.admin.pendingCount })
  }
}

export function useApproveUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data?: ApiApproveRequest }) =>
      approveUser(id, data ?? {}),
    onSuccess: invalidate,
  })
}

export function useRejectUser() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiRejectRequest }) =>
      rejectUser(id, data),
    onSuccess: invalidate,
  })
}

export function useAdjustUserQuota() {
  const invalidate = useInvalidateUsers()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiQuotaAdjustRequest }) =>
      adjustUserQuota(id, data),
    onSuccess: invalidate,
  })
}

export function useUsageDashboard(days = 30) {
  return useQuery({
    queryKey: queryKeys.admin.usageDashboard(days),
    queryFn: () => fetchUsageDashboard(days),
  })
}

export function useUsagePerUsers(days = 30) {
  return useQuery({
    queryKey: queryKeys.admin.usagePerUsers(days),
    queryFn: () => fetchUsagePerUsers(days),
  })
}

export function useAccountSettings() {
  return useQuery({
    queryKey: queryKeys.admin.accountSettings,
    queryFn: fetchAccountSettings,
  })
}

export function useUpdateAccountSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAccountSettingsUpdateRequest) => updateAccountSettings(data),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.accountSettings }),
  })
}
