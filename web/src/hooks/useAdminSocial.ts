import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  ApiAsrConfigUpdateRequest,
  ApiSocialAccountCreateRequest,
  ApiSocialAccountUpdateRequest,
  ApiSocialCookieImportRequest,
} from '@ai-invest/shared'

import {
  createSocialAccount,
  deleteSocialAccount,
  fetchAsrConfig,
  fetchSocialAccountsAdmin,
  fetchSocialStatus,
  importSocialCookie,
  testAsrConfig,
  updateAsrConfig,
  updateSocialAccount,
} from '@/api/adminSocial'
import { queryKeys } from '@/hooks/queryKeys'

const ACCOUNTS_KEY = queryKeys.socialAdmin.accounts
const STATUS_KEY = queryKeys.socialAdmin.status
const ASR_KEY = queryKeys.socialAdmin.asrConfig

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

export function useImportSocialCookie() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiSocialCookieImportRequest) => importSocialCookie(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: STATUS_KEY }),
  })
}

export function useAsrConfig() {
  return useQuery({
    queryKey: ASR_KEY,
    queryFn: fetchAsrConfig,
  })
}

export function useUpdateAsrConfig() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiAsrConfigUpdateRequest) => updateAsrConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ASR_KEY })
      queryClient.invalidateQueries({ queryKey: STATUS_KEY })
    },
  })
}

export function useTestAsrConfig() {
  return useMutation({
    mutationFn: () => testAsrConfig(),
  })
}
