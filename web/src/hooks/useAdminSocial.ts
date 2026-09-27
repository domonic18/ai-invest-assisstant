import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  ApiSocialAccountCreateRequest,
  ApiSocialAccountUpdateRequest,
  ApiSocialCookieImportRequest,
} from '@ai-invest/shared'

import {
  backfillSocialAccount,
  createSocialAccount,
  deleteSocialAccount,
  fetchSocialAccountPosts,
  fetchSocialAccountsAdmin,
  fetchSocialStatus,
  importSocialCookie,
  updateSocialAccount,
} from '@/api/adminSocial'
import { queryKeys } from '@/hooks/queryKeys'

const ACCOUNTS_KEY = queryKeys.socialAdmin.accounts
const STATUS_KEY = queryKeys.socialAdmin.status

export function useSocialAccountsAdmin(page: number, pageSize: number) {
  return useQuery({
    queryKey: ACCOUNTS_KEY(page, pageSize),
    queryFn: () => fetchSocialAccountsAdmin(page, pageSize),
  })
}

export function useSocialAdminStatus() {
  return useQuery({
    queryKey: STATUS_KEY,
    queryFn: fetchSocialStatus,
  })
}

export function useSocialAccountPosts(accountId: number | null) {
  return useQuery({
    queryKey: queryKeys.socialAdmin.accountPosts(accountId ?? 0),
    queryFn: () => fetchSocialAccountPosts(accountId as number),
    enabled: accountId !== null,
  })
}

export function useCreateSocialAccount(page: number, pageSize: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiSocialAccountCreateRequest) => createSocialAccount(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_KEY(page, pageSize) })
      queryClient.invalidateQueries({ queryKey: STATUS_KEY })
    },
  })
}

export function useUpdateSocialAccount(page: number, pageSize: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ApiSocialAccountUpdateRequest }) =>
      updateSocialAccount(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_KEY(page, pageSize) })
      queryClient.invalidateQueries({ queryKey: STATUS_KEY })
    },
  })
}

export function useDeleteSocialAccount(page: number, pageSize: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteSocialAccount(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_KEY(page, pageSize) })
    },
  })
}

export function useBackfillSocialAccount(page: number, pageSize: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => backfillSocialAccount(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_KEY(page, pageSize) })
      queryClient.invalidateQueries({ queryKey: STATUS_KEY })
    },
  })
}

export function useImportSocialCookie() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiSocialCookieImportRequest) => importSocialCookie(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: STATUS_KEY }),
  })
}

