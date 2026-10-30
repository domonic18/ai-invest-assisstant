import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import type { ApiKeyCreateRequest } from '@ai-invest/shared'

import {
  createMyApiKey,
  fetchMyApiKeys,
  purgeMyApiKey,
  revokeMyApiKey,
} from '@/api/apiKeys'
import { queryKeys } from '@/hooks/queryKeys'

export function useMyApiKeys() {
  return useQuery({
    queryKey: queryKeys.users.apiKeys,
    queryFn: fetchMyApiKeys,
    staleTime: 30_000,
  })
}

export function useCreateMyApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ApiKeyCreateRequest) => createMyApiKey(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users.apiKeys })
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export function useRevokeMyApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (keyId: number) => revokeMyApiKey(keyId),
    onSuccess: () => {
      message.success('已吊销该密钥')
      void queryClient.invalidateQueries({ queryKey: queryKeys.users.apiKeys })
    },
    onError: (error: Error) => message.error(error.message),
  })
}

export function usePurgeMyApiKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (keyId: number) => purgeMyApiKey(keyId),
    onSuccess: () => {
      message.success('已删除该密钥记录')
      void queryClient.invalidateQueries({ queryKey: queryKeys.users.apiKeys })
    },
    onError: (error: Error) => message.error(error.message),
  })
}
